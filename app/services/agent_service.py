"""A small, approval-aware agent loop for local Ollama models."""

from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from threading import RLock, Thread
from typing import Any
from uuid import UUID, uuid4
import json
import logging

from app.agents.agent_protocol import AgentProtocol
from app.agents.ollama_agent import OllamaAgent
from app.core.settings import settings
from app.core.redaction import redact_value
from app.tools.agent_tools import AgentToolExecutor
from app.services.project_memory_service import ProjectMemoryService
from app.services.project_guidance_service import ProjectGuidanceService
from app.services.project_skill_service import ProjectSkillService
from app.services.operations_service import OperationsService, UsageLimitError
from app.workspace.file_manager import FileManager


DEFAULT_AGENT_MAX_STEPS = 8
DEFAULT_PROJECT_MAX_STEPS = 60
DEFAULT_DELIVERY_MAX_STEPS = 48
DEFAULT_TEAM_MAX_STEPS = 24
DEFAULT_REVIEW_MAX_STEPS = 16
MAX_AGENT_STEPS = 12
MAX_PROJECT_STEPS = 60
MAX_DELIVERY_STEPS = 60
MAX_TEAM_STEPS = 36
MAX_REVIEW_STEPS = 24
MAX_MODEL_TOOL_RESULT_CHARS = 3_600
logger = logging.getLogger(__name__)


TEAM_MEMBER_DEFINITIONS = (
    {
        "id": "researcher",
        "name": "Research",
        "instruction": (
            "Explore only. Inspect the relevant project files, entry points, conventions, and risks. "
            "Do not write files, initialize Git, create branches, commit, restore files, or run commands. "
            "Finish with a concise handoff containing findings and a smallest safe implementation plan."
        ),
    },
    {
        "id": "implementer",
        "name": "Implement",
        "instruction": (
            "Implement the requested change using the research handoff as context. Inspect additional files only when needed. "
            "Keep edits focused and request approval before every write, Git mutation, browser capture, or command. "
            "Finish with a concise handoff describing exactly what changed and what still needs verification."
        ),
    },
    {
        "id": "reviewer",
        "name": "Review",
        "instruction": (
            "Review and verify only. Inspect the changed files and Git diff, identify the relevant checks, and request approval "
            "for a targeted test or browser check when it is needed. Do not edit files or mutate Git. "
            "Finish with evidence, remaining risks, and any manual next step."
        ),
    },
)

TEAM_READ_ONLY_TOOLS = {
    "list_files",
    "inspect_project",
    "find_code",
    "read_project_guidance",
    "list_project_skills",
    "read_project_skill",
    "detect_project_checks",
    "read_file",
    "search_code",
    "git_status",
    "git_diff",
    "git_log",
}
TEAM_REVIEW_TOOLS = TEAM_READ_ONLY_TOOLS | {
    "capture_browser_qa",
    "git_review_diff",
    "run_project_command",
    "run_tests",
}


@dataclass
class AgentRun:
    run_id: str
    task: str
    max_steps: int
    messages: list[dict[str, str]]
    mode: str = "agent"
    owner_id: str | None = None
    workspace_id: str = "main"
    project_id: str = "workspace"
    memory_saved: bool = False
    trace: list[dict[str, Any]] = field(default_factory=list)
    status: str = "running"
    answer: str | None = None
    pending_action: dict[str, Any] | None = None
    project_plan: dict[str, Any] | None = None
    attachments: list[str] = field(default_factory=list)
    system_prompt: str = ""
    team_members: list[dict[str, Any]] = field(default_factory=list)
    team_member_index: int = 0
    background: bool = False
    workspace_path: str = ""
    approved_action: dict[str, Any] | None = None
    cancel_requested: bool = False
    review_scope: str = "uncommitted"
    review_target: str = ""
    delivery_phase: str = ""
    delivery_final_answer: str = ""
    quota_exempt: bool = False
    activity: dict[str, Any] | None = None


class AgentService:
    _runs: dict[str, AgentRun] = {}
    _lock = RLock()
    _background_queue: deque[str] = deque()
    _queued_background_runs: set[str] = set()
    _background_workers: set[str] = set()
    _state_root = Path(settings.agent_state_root).expanduser().resolve()

    @classmethod
    def active_run_count(cls, owner_id: str) -> int:
        """Return only the caller's active jobs; no cross-user queue details leak."""
        with cls._lock:
            return sum(
                1
                for run in cls._runs.values()
                if run.owner_id == owner_id and run.status in {"queued", "running", "cancelling", "awaiting_approval"}
            )

    @classmethod
    def start(
        cls,
        task: str,
        max_steps: int | None = None,
        mode: str = "agent",
        attachments: list[str] | None = None,
        owner_id: str | None = None,
        workspace_id: str = "main",
        project_id: str = "workspace",
        background: bool = False,
        review_scope: str = "uncommitted",
        review_target: str = "",
        quota_exempt: bool = False,
    ) -> dict[str, Any]:
        task = task.strip()
        if not task:
            raise ValueError("task must not be empty")
        if mode not in {"agent", "project", "expert", "delivery", "team", "review"}:
            raise ValueError("mode must be agent, project, expert, delivery, team, or review")
        if review_scope not in {"uncommitted", "staged", "commit", "branch"}:
            raise ValueError("review scope must be uncommitted, staged, commit, or branch")
        if not isinstance(review_target, str):
            raise ValueError("review target must be text")
        review_target = review_target.strip()
        if mode == "review" and review_scope in {"commit", "branch"} and not review_target:
            raise ValueError(f"review target is required for {review_scope} review")
        attachment_paths = cls._attachment_paths(attachments or [])
        try:
            OperationsService.reserve_run(owner_id, quota_exempt=quota_exempt)
        except UsageLimitError as error:
            raise ValueError(str(error)) from error

        if max_steps is None:
            if mode in {"project", "expert"}:
                max_steps = DEFAULT_PROJECT_MAX_STEPS
            elif mode == "delivery":
                max_steps = DEFAULT_DELIVERY_MAX_STEPS
            elif mode == "team":
                max_steps = DEFAULT_TEAM_MAX_STEPS
            elif mode == "review":
                max_steps = DEFAULT_REVIEW_MAX_STEPS
            else:
                max_steps = DEFAULT_AGENT_MAX_STEPS
        if mode in {"project", "expert"}:
            step_limit = MAX_PROJECT_STEPS
        elif mode == "delivery":
            step_limit = MAX_DELIVERY_STEPS
        elif mode == "team":
            step_limit = MAX_TEAM_STEPS
        elif mode == "review":
            step_limit = MAX_REVIEW_STEPS
        else:
            step_limit = MAX_AGENT_STEPS
        max_steps = max(1, min(max_steps, step_limit))
        memory_context = ProjectMemoryService.context() if owner_id is not None else ""
        guidance_context = ProjectGuidanceService.context() if owner_id is not None else ""
        skills_context = ProjectSkillService.context() if owner_id is not None else ""
        system_prompt = cls._system_prompt(
            mode,
            memory_context,
            guidance_context,
            skills_context,
            review_scope,
            review_target,
        )
        run = AgentRun(
            run_id=str(uuid4()),
            task=task,
            max_steps=max_steps,
            mode=mode,
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
            attachments=attachment_paths,
            messages=[],
            system_prompt=system_prompt,
            team_members=cls._team_members() if mode == "team" else [],
            background=background,
            workspace_path=str(FileManager.workspace()),
            review_scope=review_scope,
            review_target=review_target,
            quota_exempt=quota_exempt,
        )
        if mode == "team":
            cls._prepare_next_team_member(run)
        else:
            cls._prepare_single_agent(run)

        with cls._lock:
            cls._runs[run.run_id] = run
        cls._audit(run, "run_started", outcome="queued" if background else "running")

        if run.background:
            run.status = "queued"
            cls._save_run(run)
            cls._schedule_background(run)
            return cls._serialize(run)

        cls._continue(run)
        cls._record_project_memory(run)
        cls._save_run(run)
        return cls._serialize(run)

    @classmethod
    def get(
        cls,
        run_id: str,
        owner_id: str | None = None,
        workspace_id: str | None = None,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        run = cls._get_run(run_id, owner_id)
        if workspace_id is not None and run.workspace_id != workspace_id:
            raise ValueError("run belongs to a different worktree")
        if project_id is not None and run.project_id != project_id:
            raise ValueError("run belongs to a different project")
        return cls._serialize(run)

    @classmethod
    def resume(
        cls,
        run_id: str,
        approve: bool,
        owner_id: str | None = None,
        workspace_id: str | None = None,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        run = cls._get_run(run_id, owner_id)

        if workspace_id is not None and run.workspace_id != workspace_id:
            raise ValueError("run belongs to a different worktree")
        if project_id is not None and run.project_id != project_id:
            raise ValueError("run belongs to a different project")

        if run.status != "awaiting_approval" or run.pending_action is None:
            raise ValueError("run is not waiting for an approval")

        action = run.pending_action
        run.pending_action = None

        if not approve:
            run.status = "cancelled"
            run.answer = "The pending action was rejected. No changes were made."
            if run.mode == "team":
                cls._current_team_member(run)["status"] = "cancelled"
            run.trace.append(
                {
                    "step": len(run.trace) + 1,
                    "tool": action["tool"],
                    "status": "rejected",
                    **cls._team_action_metadata(run),
                }
            )
            cls._audit(run, "approval_rejected", outcome="cancelled", detail=action["tool"])
            cls._record_project_memory(run)
            cls._save_run(run)
            return cls._serialize(run)

        if run.background:
            run.approved_action = action
            run.status = "queued"
            cls._audit(run, "approval_granted", outcome="queued", detail=action["tool"])
            cls._save_run(run)
            cls._schedule_background(run)
            return cls._serialize(run)

        if run.mode == "team":
            cls._current_team_member(run)["status"] = "running"
        cls._execute_action(run, action)
        if run.mode == "delivery" and run.delivery_phase == "verification_pending":
            cls._finish_delivery(run)
        else:
            cls._continue(run)
        cls._record_project_memory(run)
        cls._save_run(run)
        return cls._serialize(run)

    @classmethod
    def cancel(
        cls,
        run_id: str,
        owner_id: str | None = None,
        workspace_id: str | None = None,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        run = cls._get_run(run_id, owner_id)
        if workspace_id is not None and run.workspace_id != workspace_id:
            raise ValueError("run belongs to a different worktree")
        if project_id is not None and run.project_id != project_id:
            raise ValueError("run belongs to a different project")
        if not run.background or run.status not in {"queued", "running", "cancelling"}:
            raise ValueError("only a queued or running background run can be cancelled")

        run.cancel_requested = True
        if run.status == "queued":
            cls._mark_cancelled(run)
        else:
            run.status = "cancelling"
            run.answer = "Cancellation requested. The current Ollama response will finish before no further actions run."
        cls._save_run(run)
        cls._audit(run, "run_cancel_requested", outcome=run.status)
        return cls._serialize(run)

    @classmethod
    def continue_run(
        cls,
        run_id: str,
        owner_id: str | None = None,
        workspace_id: str | None = None,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        """Continue a persisted goal without bypassing normal tool approvals."""
        run = cls._get_run(run_id, owner_id)
        if workspace_id is not None and run.workspace_id != workspace_id:
            raise ValueError("run belongs to a different worktree")
        if project_id is not None and run.project_id != project_id:
            raise ValueError("run belongs to a different project")
        if run.status != "needs_input":
            raise ValueError("only a run that needs input can be continued")

        run.cancel_requested = False
        run.pending_action = None
        run.approved_action = None
        if run.mode == "delivery":
            run.delivery_phase = ""
            run.delivery_final_answer = ""
        cls._audit(run, "run_continued", outcome="queued" if run.background else "running")
        if run.background:
            run.status = "queued"
            cls._save_run(run)
            cls._schedule_background(run)
            return cls._serialize(run)

        cls._continue(run)
        cls._record_project_memory(run)
        cls._save_run(run)
        return cls._serialize(run)

    @classmethod
    def _schedule_background(cls, run: AgentRun) -> None:
        with cls._lock:
            if run.run_id in cls._background_workers or run.run_id in cls._queued_background_runs:
                return
            cls._background_queue.append(run.run_id)
            cls._queued_background_runs.add(run.run_id)
            cls._start_queued_workers_locked()

    @classmethod
    def _start_queued_workers_locked(cls) -> None:
        """Start background workers in submission order without competing for Ollama."""
        limit = max(1, settings.agent_max_concurrent_runs)
        while len(cls._background_workers) < limit and cls._background_queue:
            run_id = cls._background_queue.popleft()
            cls._queued_background_runs.discard(run_id)
            run = cls._runs.get(run_id)
            if run is None or not run.background or run.status != "queued" or run.cancel_requested:
                continue
            cls._background_workers.add(run_id)
            worker = Thread(target=cls._run_background, args=(run_id,), daemon=True, name=f"mycodexai-{run_id[:8]}")
            worker.start()

    @classmethod
    def _run_background(cls, run_id: str) -> None:
        try:
            run = cls._get_run(run_id)
            if run.cancel_requested:
                cls._mark_cancelled(run)
                cls._save_run(run)
                return

            workspace = Path(run.workspace_path)
            if not workspace.is_dir():
                run.status = "failed"
                run.answer = "The project workspace is no longer available."
                cls._record_project_memory(run)
                cls._save_run(run)
                return

            run.status = "running"
            if run.mode == "team":
                cls._current_team_member(run)["status"] = "running"
            cls._save_run(run)
            token = FileManager.activate_workspace(workspace)
            try:
                if run.approved_action is not None:
                    action = run.approved_action
                    run.approved_action = None
                    cls._execute_action(run, action)
                if run.cancel_requested:
                    cls._mark_cancelled(run)
                elif run.mode == "delivery" and run.delivery_phase == "verification_pending":
                    cls._finish_delivery(run)
                else:
                    cls._continue(run)
            finally:
                FileManager.reset_workspace(token)

            cls._record_project_memory(run)
            cls._save_run(run)
        except Exception as error:
            logger.exception("Background agent run %s failed", run_id)
            try:
                run = cls._get_run(run_id)
                run.status = "failed"
                run.answer = f"Background agent worker failed: {error}"
                cls._record_project_memory(run)
                cls._save_run(run)
            except (KeyError, OSError, ValueError):
                pass
        finally:
            with cls._lock:
                cls._background_workers.discard(run_id)
                cls._start_queued_workers_locked()

    @classmethod
    def _mark_cancelled(cls, run: AgentRun) -> None:
        run.status = "cancelled"
        run.pending_action = None
        run.approved_action = None
        run.answer = "The background agent run was cancelled. No further actions were run."
        if run.mode == "team":
            cls._current_team_member(run)["status"] = "cancelled"
        cls._audit(run, "run_cancelled", outcome="cancelled")

    @classmethod
    def _continue(cls, run: AgentRun) -> None:
        run.status = "running"

        while len(run.trace) < run.max_steps:
            if run.cancel_requested:
                cls._mark_cancelled(run)
                return
            try:
                OperationsService.consume_step(run.owner_id, quota_exempt=run.quota_exempt)
            except UsageLimitError as error:
                run.status = "needs_input"
                run.answer = str(error)
                run.trace.append(
                    {
                        "step": len(run.trace) + 1,
                        "tool": "budget",
                        "status": "limit_reached",
                        "summary": "The daily agent safety budget was reached before another model decision.",
                    }
                )
                cls._audit(run, "daily_step_limit_reached", outcome="needs_input")
                return
            try:
                run.activity = {
                    "state": "thinking",
                    "message": "Ollama กำลังวิเคราะห์คำสั่ง…",
                }
                cls._save_run(run)

                def observe_resources(snapshot: dict[str, Any] | None) -> None:
                    if snapshot is None:
                        run.activity = {
                            "state": "thinking",
                            "message": "Ollama กำลังวิเคราะห์คำสั่ง…",
                        }
                    else:
                        available = snapshot.get("available_memory_mb")
                        minimum = snapshot.get("min_available_mb")
                        run.activity = {
                            "state": "waiting_for_memory",
                            "message": "กำลังรอ RAM ว่างก่อนเริ่ม Ollama เพื่อป้องกันเครื่องค้าง…",
                            "available_memory_mb": available,
                            "min_available_mb": minimum,
                        }
                    cls._save_run(run)

                with OllamaAgent.observe_resources(observe_resources):
                    raw_response = OllamaAgent.ask_json(run.messages)
                run.activity = None
            except Exception as error:
                run.activity = None
                run.status = "failed"
                run.answer = f"Ollama request failed: {error}"
                return

            if run.cancel_requested:
                cls._mark_cancelled(run)
                return

            decision = AgentProtocol.parse(raw_response)
            if decision is None:
                run.status = "failed"
                run.answer = "Ollama did not return a valid agent JSON action."
                run.trace.append(
                    {
                        "step": len(run.trace) + 1,
                        "tool": None,
                        "status": "invalid_response",
                        "raw_response": raw_response[:2_000],
                    }
                )
                return

            tool_name = decision["tool"]
            if tool_name == "final":
                if run.mode == "team":
                    answer = str(decision["arguments"].get("answer") or decision["summary"] or "No handoff was provided.")
                    cls._complete_team_member(run, answer)
                    if run.status == "completed":
                        return
                    continue
                answer = str(decision["arguments"].get("answer") or decision["summary"] or "Task completed.")
                if run.mode == "delivery":
                    cls._begin_delivery_verification(run, answer)
                    return
                run.status = "completed"
                run.answer = answer
                run.trace.append(
                    {
                        "step": len(run.trace) + 1,
                        "tool": "final",
                        "status": "completed",
                    }
                )
                cls._audit(run, "run_completed", outcome="completed")
                return

            tool = AgentToolExecutor.get(tool_name)
            if tool is None:
                run.status = "failed"
                run.answer = f"Ollama requested an unsupported tool: {tool_name}"
                run.trace.append(
                    {
                        "step": len(run.trace) + 1,
                        "tool": tool_name,
                        "status": "blocked",
                    }
                )
                return

            if not cls._team_tool_allowed(run, tool_name):
                result = {
                    "status": "blocked",
                    "reason": (
                        f"The {cls._current_team_member(run)['name']} role cannot use {tool_name}. "
                        "Finish the assigned role or hand off to the next role."
                    ),
                }
                cls._append_action_result(run, tool_name, decision.get("summary", ""), result)
                continue

            action = {
                "tool": tool_name,
                "arguments": decision["arguments"],
                "summary": decision["summary"],
            }

            if tool.requires_approval:
                try:
                    preview = AgentToolExecutor.preview(tool_name, decision["arguments"])
                except (TypeError, ValueError) as error:
                    run.status = "failed"
                    run.answer = f"Invalid arguments for {tool_name}: {error}"
                    return

                run.status = "awaiting_approval"
                if run.mode == "team":
                    cls._current_team_member(run)["status"] = "awaiting_approval"
                run.pending_action = {
                    **action,
                    "preview": preview,
                    **cls._team_action_metadata(run),
                }
                run.trace.append(
                    {
                        "step": len(run.trace) + 1,
                        "tool": tool_name,
                        "status": "awaiting_approval",
                        "summary": decision["summary"],
                        "preview": preview,
                        **cls._team_action_metadata(run),
                    }
                )
                return

            cls._execute_action(run, action)

        run.status = "needs_input"
        if run.mode == "team":
            current = cls._current_team_member(run)
            current["status"] = "needs_input"
            run.answer = (
                f"Team stopped after {run.max_steps} total tool steps while {current['name']} was working. "
                "Review the handoffs and continue with a narrower task."
            )
        else:
            run.answer = f"Stopped after {run.max_steps} tool steps. Review the trace and continue with a narrower task."

    @classmethod
    def _execute_action(cls, run: AgentRun, action: dict[str, Any]) -> None:
        run.activity = {
            "state": "executing",
            "message": cls._tool_activity_message(action["tool"]),
            "detail": str(action.get("summary") or ""),
        }
        cls._save_run(run)
        try:
            result = AgentToolExecutor.execute(action["tool"], action["arguments"])
        except (OSError, TypeError, ValueError) as error:
            result = {
                "status": "failed",
                "reason": str(error),
            }
        run.activity = None
        cls._append_action_result(run, action["tool"], action.get("summary", ""), result)
        if action["tool"] == "set_project_plan" and result.get("status") == "planned":
            run.project_plan = result.get("plan")

    @classmethod
    def _append_action_result(
        cls,
        run: AgentRun,
        tool_name: str,
        summary: str,
        result: dict[str, Any],
    ) -> None:
        run.trace.append(
            {
                "step": len(run.trace) + 1,
                "tool": tool_name,
                "status": result.get("status", "ok"),
                "summary": summary,
                "result": result,
                **cls._team_action_metadata(run),
            }
        )
        run.messages.append(
            {
                "role": "user",
                "content": "Tool result:\n" + json.dumps(cls._result_for_model(result), ensure_ascii=False),
            }
        )

    @staticmethod
    def _result_for_model(result: dict[str, Any]) -> dict[str, Any]:
        """Keep tool evidence useful without overflowing a local model context."""
        try:
            compact = json.loads(json.dumps(result, ensure_ascii=False))
        except (TypeError, ValueError):
            return {"status": "unavailable", "notice": "The tool result could not be encoded for the model."}

        serialized = json.dumps(compact, ensure_ascii=False)
        if len(serialized) <= MAX_MODEL_TOOL_RESULT_CHARS:
            return compact

        for key, value in list(compact.items()):
            if isinstance(value, list) and len(value) > 20:
                compact[key] = value[:20]
                compact[f"{key}_truncated_for_model"] = True
            elif isinstance(value, str) and len(value) > 1_200:
                compact[key] = value[:1_200] + "\n… output truncated for model context …"
                compact[f"{key}_truncated_for_model"] = True

        if len(json.dumps(compact, ensure_ascii=False)) <= MAX_MODEL_TOOL_RESULT_CHARS:
            return compact

        return {
            "status": compact.get("status", "ok"),
            "notice": "Tool result was large and is available in the run trace. Use a narrower tool query for details.",
            "available_keys": sorted(compact.keys())[:20],
            "truncated_for_model": True,
        }

    @staticmethod
    def _tool_activity_message(tool_name: str) -> str:
        labels = {
            "list_files": "กำลังดูรายการไฟล์…",
            "inspect_project": "กำลังสำรวจโครงสร้างโปรเจกต์…",
            "find_code": "กำลังค้นหาโค้ดที่เกี่ยวข้อง…",
            "search_code": "กำลังค้นหาโค้ด…",
            "read_file": "กำลังอ่านไฟล์ที่เกี่ยวข้อง…",
            "read_project_guidance": "กำลังอ่านคำแนะนำของโปรเจกต์…",
            "list_project_skills": "กำลังตรวจสอบ Project Skills…",
            "read_project_skill": "กำลังอ่าน Project Skill…",
            "set_project_plan": "กำลังบันทึกแผนงาน…",
            "write_file": "กำลังเขียนไฟล์ที่อนุมัติแล้ว…",
            "write_files": "กำลังเขียนชุดไฟล์ที่อนุมัติแล้ว…",
            "run_project_command": "กำลังรันคำสั่งที่อนุมัติแล้ว…",
            "run_tests": "กำลังทดสอบโปรเจกต์…",
            "git_status": "กำลังตรวจสอบสถานะ Git…",
            "git_diff": "กำลังตรวจสอบความเปลี่ยนแปลง Git…",
            "git_initialize": "กำลังเริ่มต้น Git repository…",
            "git_commit": "กำลังสร้าง Git commit ที่อนุมัติแล้ว…",
            "capture_browser_qa": "กำลังตรวจสอบหน้าเว็บด้วยเบราว์เซอร์…",
        }
        return labels.get(tool_name, "กำลังทำขั้นตอนที่อนุมัติแล้ว…")

    @classmethod
    def _begin_delivery_verification(cls, run: AgentRun, answer: str) -> None:
        """Require concrete checks after a delivery task edits code.

        The model may still choose its own checks while it works.  This deterministic
        final gate makes sure a completed Delivery run always captures a project check
        when one is detectable and a Git review snapshot before it reports success.
        """
        run.delivery_final_answer = answer
        run.delivery_phase = "planning_verification"
        changed_files = any(
            entry.get("tool") in {"write_file", "write_files"} and entry.get("status") == "written"
            for entry in run.trace
        )
        if not changed_files:
            cls._finish_delivery(run, note="No approved file write was recorded; captured the final Git review only.")
            return

        checks = AgentToolExecutor.execute("detect_project_checks", {})
        cls._append_action_result(
            run,
            "detect_project_checks",
            "Delivery workflow detected the project's verification commands.",
            checks,
        )
        recommended = checks.get("recommended") if isinstance(checks, dict) else None
        command = recommended[0].get("command") if isinstance(recommended, list) and recommended and isinstance(recommended[0], dict) else None
        if not isinstance(command, list) or not command:
            cls._finish_delivery(run, note="No supported project test or build command was detected.")
            return

        action = {
            "tool": "run_project_command",
            "arguments": {"command": command},
            "summary": "Delivery workflow requires this detected project check before completion.",
        }
        try:
            preview = AgentToolExecutor.preview(action["tool"], action["arguments"])
        except (TypeError, ValueError) as error:
            cls._finish_delivery(run, note=f"The detected verification command could not be prepared safely: {error}")
            return

        run.delivery_phase = "verification_pending"
        run.status = "awaiting_approval"
        run.pending_action = {**action, "preview": preview, "delivery_verification": True}
        run.trace.append(
            {
                "step": len(run.trace) + 1,
                "tool": action["tool"],
                "status": "awaiting_approval",
                "summary": action["summary"],
                "preview": preview,
                "delivery_verification": True,
            }
        )
        cls._audit(run, "delivery_verification_requested", outcome="awaiting_approval", detail="run_project_command")

    @classmethod
    def _finish_delivery(cls, run: AgentRun, note: str = "") -> None:
        verification = cls._last_delivery_verification(run)
        if verification is not None and verification.get("status") != "ok":
            run.delivery_phase = "verification_failed"
            run.status = "needs_input"
            run.answer = (
                f"{run.delivery_final_answer}\n\nDelivery verification did not pass ({verification.get('status')}). "
                "Inspect the trace, fix the issue, then use Continue to let the agent proceed."
            )
            cls._audit(run, "delivery_verification_failed", outcome="needs_input", detail=str(verification.get("status")))
            return

        status = AgentToolExecutor.execute("git_status", {})
        cls._append_action_result(run, "git_status", "Delivery workflow captured the final Git status.", status)
        review = AgentToolExecutor.execute("git_review_diff", {"scope": "uncommitted", "target": ""})
        cls._append_action_result(run, "git_review_diff", "Delivery workflow captured a read-only final diff review.", review)

        summaries = []
        if verification is not None:
            command = verification.get("command") or []
            summaries.append("Verification passed" + (f": {' '.join(command)}" if command else "."))
        if note:
            summaries.append(note)
        if review.get("status") == "ok":
            summaries.append("A final Git diff review was captured in the trace.")
        else:
            summaries.append("Git review was unavailable; inspect the trace before committing.")

        run.delivery_phase = "completed"
        run.status = "completed"
        run.answer = f"{run.delivery_final_answer}\n\nDelivery checks: " + " ".join(summaries)
        run.trace.append(
            {
                "step": len(run.trace) + 1,
                "tool": "final",
                "status": "completed",
                "summary": "Delivery workflow completed after verification and review.",
            }
        )
        cls._audit(run, "delivery_completed", outcome="completed")

    @staticmethod
    def _last_delivery_verification(run: AgentRun) -> dict[str, Any] | None:
        for entry in reversed(run.trace):
            if entry.get("tool") == "run_project_command" and entry.get("status") != "awaiting_approval":
                result = entry.get("result")
                return result if isinstance(result, dict) else {"status": entry.get("status", "failed")}
        return None

    @staticmethod
    def _audit(run: AgentRun, event: str, outcome: str = "", detail: str = "") -> None:
        OperationsService.record(
            run.owner_id,
            event,
            run_id=run.run_id,
            mode=run.mode,
            workspace_id=run.workspace_id,
            project_id=run.project_id,
            outcome=outcome,
            detail=detail,
        )

    @classmethod
    def _get_run(cls, run_id: str, owner_id: str | None = None) -> AgentRun:
        with cls._lock:
            run = cls._runs.get(run_id)

        if run is None:
            run = cls._load_run(run_id)
            if run is not None:
                with cls._lock:
                    cls._runs[run.run_id] = run

        if run is None:
            raise KeyError(run_id)
        if owner_id is not None and run.owner_id != owner_id:
            raise KeyError(run_id)

        return run

    @staticmethod
    def _serialize(run: AgentRun) -> dict[str, Any]:
        queue = AgentService._queue_details(run)
        return {
            "run_id": run.run_id,
            "task": run.task,
            "mode": run.mode,
            "background": run.background,
            "review_scope": run.review_scope,
            "review_target": run.review_target,
            "workspace_id": run.workspace_id,
            "project_id": run.project_id,
            "status": run.status,
            "answer": run.answer,
            "trace": run.trace,
            "pending_action": run.pending_action,
            "project_plan": run.project_plan,
            "team_members": run.team_members,
            "attachments": run.attachments,
            "delivery_phase": run.delivery_phase,
            "activity": run.activity,
            "progress": {
                "completed_steps": len(run.trace),
                "max_steps": run.max_steps,
                "has_pending_approval": run.pending_action is not None,
                "delivery_phase": run.delivery_phase,
                **queue,
            },
        }

    @classmethod
    def _queue_details(cls, run: AgentRun) -> dict[str, int | None]:
        """Expose only this run's position and aggregate depth, never other users' details."""
        if not run.background:
            return {"queue_position": None, "queue_total": 0}
        with cls._lock:
            active_count = len(cls._background_workers)
            queued_ids = [
                run_id
                for run_id in cls._background_queue
                if (candidate := cls._runs.get(run_id)) is not None
                and candidate.status == "queued"
                and not candidate.cancel_requested
            ]
            if run.run_id in cls._background_workers:
                return {"queue_position": 0, "queue_total": active_count + len(queued_ids)}
            if run.run_id in queued_ids:
                return {
                    "queue_position": queued_ids.index(run.run_id) + 1,
                    "queue_total": active_count + len(queued_ids),
                }
        return {"queue_position": None, "queue_total": 0}

    @classmethod
    def _save_run(cls, run: AgentRun) -> None:
        state_path = cls._state_path(run.run_id)
        if state_path is None:
            return

        payload = cls._serialize(run)
        payload["messages"] = run.messages
        payload["owner_id"] = run.owner_id
        payload["memory_saved"] = run.memory_saved
        payload["system_prompt"] = run.system_prompt
        payload["team_member_index"] = run.team_member_index
        payload["background"] = run.background
        payload["workspace_path"] = run.workspace_path
        payload["approved_action"] = run.approved_action
        payload["cancel_requested"] = run.cancel_requested
        payload["review_scope"] = run.review_scope
        payload["review_target"] = run.review_target
        payload["delivery_phase"] = run.delivery_phase
        payload["delivery_final_answer"] = run.delivery_final_answer
        payload["quota_exempt"] = run.quota_exempt
        # Resume state can include model messages and tool evidence.  Keep it
        # useful after a restart without turning the run directory into a
        # second credentials store if a task, output, or attachment mentions a
        # common secret format.
        payload = redact_value(payload)
        temporary_path = state_path.with_suffix(".tmp")

        try:
            state_path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            temporary_path.replace(state_path)
        except OSError as error:
            logger.warning("Could not persist agent run %s: %s", run.run_id, error)

    @classmethod
    def _load_run(cls, run_id: str) -> AgentRun | None:
        state_path = cls._state_path(run_id)
        if state_path is None or not state_path.is_file():
            return None

        try:
            payload = json.loads(state_path.read_text(encoding="utf-8"))
            if payload.get("run_id") != run_id:
                return None
            run = AgentRun(
                run_id=run_id,
                task=str(payload["task"]),
                max_steps=int(payload["progress"]["max_steps"]),
                messages=payload["messages"],
                mode=str(payload.get("mode", "agent")),
                owner_id=payload.get("owner_id"),
                workspace_id=str(payload.get("workspace_id", "main")),
                project_id=str(payload.get("project_id", "workspace")),
                memory_saved=bool(payload.get("memory_saved", False)),
                trace=payload.get("trace", []),
                status=str(payload.get("status", "failed")),
                answer=payload.get("answer"),
                pending_action=payload.get("pending_action"),
                project_plan=payload.get("project_plan"),
                attachments=payload.get("attachments", []),
                system_prompt=str(
                    payload.get("system_prompt")
                    or (payload.get("messages") or [{"content": ""}])[0].get("content", "")
                ),
                team_members=payload.get("team_members", []),
                team_member_index=int(payload.get("team_member_index", 0)),
                background=bool(payload.get("background", False)),
                workspace_path=str(payload.get("workspace_path") or FileManager.workspace()),
                approved_action=payload.get("approved_action"),
                cancel_requested=bool(payload.get("cancel_requested", False)),
                review_scope=str(payload.get("review_scope", "uncommitted")),
                review_target=str(payload.get("review_target", "")),
                delivery_phase=str(payload.get("delivery_phase", "")),
                delivery_final_answer=str(payload.get("delivery_final_answer", "")),
                quota_exempt=bool(payload.get("quota_exempt", False)),
                activity=payload.get("activity") if isinstance(payload.get("activity"), dict) else None,
            )
            if run.background and run.status in {"queued", "running", "cancelling"}:
                run.status = "needs_input"
                run.cancel_requested = False
                run.approved_action = None
                run.answer = "The app restarted while this background run was active. Review the trace and start a new run."
            return run
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
            logger.warning("Could not restore agent run %s: %s", run_id, error)
            return None

    @staticmethod
    def _state_path(run_id: str) -> Path | None:
        try:
            normalized_run_id = str(UUID(run_id))
        except ValueError:
            return None
        return AgentService._state_root / f"{normalized_run_id}.json"

    @staticmethod
    def _attachment_paths(attachments: list[str]) -> list[str]:
        if len(attachments) > 100:
            raise ValueError("attachments must contain at most 100 paths")

        normalized_paths: list[str] = []
        seen_paths: set[str] = set()
        for attachment in attachments:
            if not isinstance(attachment, str) or not attachment.strip():
                raise ValueError("every attachment must be a non-empty workspace-relative path")

            path = FileManager._resolve_path(attachment)
            if path is None or not path.is_file():
                raise ValueError(f"attachment is not an available workspace file: {attachment}")

            relative_path = path.relative_to(FileManager.workspace()).as_posix()
            if relative_path.casefold() in seen_paths:
                continue
            seen_paths.add(relative_path.casefold())
            normalized_paths.append(relative_path)

        return normalized_paths

    @staticmethod
    def _task_with_attachments(task: str, attachments: list[str]) -> str:
        if not attachments:
            return task

        return (
            task
            + "\n\nUser-uploaded workspace files to inspect before making changes:\n"
            + json.dumps(attachments, ensure_ascii=False)
        )

    @staticmethod
    def _team_members() -> list[dict[str, Any]]:
        return [
            {
                "id": definition["id"],
                "name": definition["name"],
                "status": "pending",
                "summary": None,
            }
            for definition in TEAM_MEMBER_DEFINITIONS
        ]

    @classmethod
    def _prepare_single_agent(cls, run: AgentRun) -> None:
        run.messages = [
            {"role": "system", "content": run.system_prompt},
            {"role": "user", "content": cls._task_with_attachments(run.task, run.attachments)},
        ]

    @classmethod
    def _prepare_next_team_member(cls, run: AgentRun) -> None:
        if run.team_member_index >= len(run.team_members):
            return

        member = run.team_members[run.team_member_index]
        definition = next(item for item in TEAM_MEMBER_DEFINITIONS if item["id"] == member["id"])
        member["status"] = "running"
        handoffs = [
            {"role": item["name"], "summary": item["summary"]}
            for item in run.team_members[:run.team_member_index]
            if item.get("summary")
        ]
        handoff_context = "No previous handoff." if not handoffs else json.dumps(handoffs, ensure_ascii=False)
        run.messages = [
            {
                "role": "system",
                "content": run.system_prompt
                + "\n\nYour assigned team role: "
                + definition["name"]
                + "\n"
                + definition["instruction"],
            },
            {
                "role": "user",
                "content": cls._task_with_attachments(run.task, run.attachments)
                + "\n\nHandoffs from earlier roles (verify against the actual project):\n"
                + handoff_context,
            },
        ]

    @classmethod
    def _complete_team_member(cls, run: AgentRun, answer: str) -> None:
        member = cls._current_team_member(run)
        member["status"] = "completed"
        member["summary"] = answer[:8_000]
        run.trace.append(
            {
                "step": len(run.trace) + 1,
                "tool": "final",
                "status": "completed",
                "summary": answer,
                **cls._team_action_metadata(run),
            }
        )
        run.team_member_index += 1
        if run.team_member_index >= len(run.team_members):
            run.status = "completed"
            run.answer = answer
            return
        cls._prepare_next_team_member(run)

    @classmethod
    def _current_team_member(cls, run: AgentRun) -> dict[str, Any]:
        if run.mode != "team" or run.team_member_index >= len(run.team_members):
            return {"id": "agent", "name": "Agent"}
        return run.team_members[run.team_member_index]

    @classmethod
    def _team_action_metadata(cls, run: AgentRun) -> dict[str, str]:
        if run.mode != "team":
            return {}
        member = cls._current_team_member(run)
        return {"team_member_id": member["id"], "team_member_name": member["name"]}

    @classmethod
    def _team_tool_allowed(cls, run: AgentRun, tool_name: str) -> bool:
        if run.mode == "review":
            return tool_name in TEAM_REVIEW_TOOLS
        if run.mode != "team":
            return True
        member_id = cls._current_team_member(run)["id"]
        if member_id == "researcher":
            return tool_name in TEAM_READ_ONLY_TOOLS
        if member_id == "reviewer":
            return tool_name in TEAM_REVIEW_TOOLS
        return True

    @classmethod
    def _record_project_memory(cls, run: AgentRun) -> None:
        if run.memory_saved or run.owner_id is None:
            return
        if ProjectMemoryService.record_run(
            run.run_id,
            run.task,
            run.status,
            run.answer,
            run.project_plan,
            run.trace,
        ):
            run.memory_saved = True

    @staticmethod
    def _system_prompt(
        mode: str,
        memory_context: str = "",
        guidance_context: str = "",
        skills_context: str = "",
        review_scope: str = "uncommitted",
        review_target: str = "",
    ) -> str:
        tools = json.dumps(AgentToolExecutor.describe(), ensure_ascii=False)
        project_builder_rules = ""
        if mode in {"project", "expert"}:
            project_builder_rules = """

Project Builder rules:
- First record a short, concrete project plan with set_project_plan.
- Use inspect_project before exploring a project with more than a few files, then use find_code and read_file to load only relevant files.
- Inspect the user-uploaded workspace files first when the task includes attachments.
- Inspect the workspace before deciding whether to create a new project folder or extend existing files.
- Build a complete project in focused write_files batches of no more than 20 related files. Continue with later batches after each approval.
- Use run_project_command only for a precise install, build, test, or package command that is needed next. It is always reviewed before execution.
- When the user requests version control for a new project, use git_initialize before creating the first reviewed files. Use git_commit only after a coherent batch has been reviewed and verified.
- Never use git_restore_file unless the user explicitly asks to discard or roll back that tracked file.
- Do not overwrite unrelated files. When the project is complete, summarize the created files, verification result, and any remaining manual setup.
"""
        expert_rules = ""
        if mode == "expert":
            expert_rules = """

Expert workflow rules:
- Work in explicit layers: understand, plan, implement, verify, then review. Do not skip from discovery directly to a completion claim.
- Before modifying an established project, use inspect_project and read_project_guidance; use find_code before reading broad sets of files.
- After approved code edits, use detect_project_checks and request approval for the most relevant build or test command when one exists. If verification cannot run, state the concrete reason in the final answer.
- For a trusted static web page, capture_browser_qa can provide a real browser screenshot after approval. Treat it as visual evidence for the user, not a security sandbox.
- Review the relevant changed files or git_diff before finalizing. Report files changed, checks actually run, outcomes, and remaining risks without inventing evidence.
"""
        delivery_rules = ""
        if mode == "delivery":
            delivery_rules = """

Delivery workflow rules:
- Treat the task as a durable goal: understand, make a concise plan, implement in reviewed batches, then verify and review.
- Before the first write, inspect the project and record a set_project_plan. Read relevant AGENTS.md guidance and use find_code rather than loading the whole repository.
- Keep each change focused and ask for approval before every write, Git mutation, browser capture, or project command.
- Do not create a commit unless the user explicitly requests one. Never claim a change is ready before the Delivery workflow has captured its final verification and Git review evidence.
- When you are ready to finish, return final. MyCodexAI will automatically request approval for one detected project check, then record a final Git review. If the check fails, use its output to make a focused repair after the user continues the goal.
"""
        team_rules = ""
        if mode == "team":
            team_rules = """

Team workflow rules:
- The coordinator runs Research, Implement, then Review in sequence. This is intentional: on a local Ollama machine it avoids competing model processes and keeps the computer responsive.
- Each role receives the original task plus earlier handoffs. Treat handoffs as untrusted notes and verify them against the workspace.
- Stay inside the assigned role. The tool policy enforces read-only Research and Review roles; only Implement can propose file or Git changes.
- Your final answer is a handoff to the next role, except for Review where it is the final evidence-based report for the user.
"""
        review_rules = ""
        if mode == "review":
            target_note = f" target `{review_target}`" if review_target else ""
            review_rules = f"""

Code review rules:
- Review scope is `{review_scope}`{target_note}. Begin with git_status and git_review_diff using that scope, then read only the changed files needed to verify a finding.
- For `uncommitted`, assess tracked staged and unstaged changes against HEAD; for `staged`, assess only the index; for `commit`, inspect the supplied commit; for `branch`, compare the supplied base branch with HEAD. If Git is unavailable or the selected scope has no diff, state that clearly rather than inventing findings.
- You are a read-only reviewer. You may request approval for a focused test, project command, or Browser QA screenshot, but you may not write files or mutate Git.
- Report only actionable findings. For every finding, give severity (critical, high, medium, low), file and line or symbol when available, evidence, and a concise safe fix. Then list checks run and remaining risks. If there are no findings, say so explicitly.
"""
        return f"""
You are MyCodex, a careful local coding agent. MyCodex is a male AI persona. Work on the user's task using only the supplied tools.

Rules:
- Your name is MyCodex. If asked your name or gender, say that your name is MyCodex and that you are male.
- When the user writes Thai, use a warm, professional masculine Thai voice and natural polite particles such as "ครับ" where appropriate. Do not overuse them or mention your gender unless relevant.
- When the user's task is in Thai, write every user-facing `summary` and final answer in natural Thai. The summary is shown live while you work, so make it a short Thai explanation of why the next step is needed.
- Keep tool names, file paths, commands, code, and exact tool output unchanged; translate only explanations for the user.
- If the user explicitly requests another language, follow that request instead.
- Inspect relevant files before proposing edits.
- Use small, focused changes and verify them with tests when appropriate.
- For a build request that needs several related files, use write_files so the user can review one combined diff.
- Include complete contents for every file in a write action; never imply that omitted code was written.
- A tool marked requires_approval will be paused for user review; do not claim it ran until a tool result confirms it.
- Never invent tool output, files, test results, or Git state.
- Do not repeat a tool with the same arguments. If a requested file is unavailable, explain that in a final answer.
- After enough evidence is collected, return a final answer rather than continuing to explore.
- Return exactly one JSON object and no Markdown.
{project_builder_rules}

{expert_rules}

{delivery_rules}

{team_rules}

{review_rules}

{memory_context}

{guidance_context}

{skills_context}

For a tool action, return:
{{"action": {{"tool": "tool_name", "arguments": {{}}}}, "summary": "why this action is next"}}

When the task is complete, return:
{{"action": {{"tool": "final", "arguments": {{"answer": "concise user-facing result"}}}}, "summary": ""}}

Available tools:
{tools}
""".strip()
