"""Approved, user-scoped shell-free project command jobs with incremental output."""

from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from threading import Event, RLock, Thread
from time import monotonic, sleep
from typing import Literal
from uuid import uuid4
import subprocess

from app.tools.agent_tools import validate_project_command
from app.services.sandbox_service import SandboxError, SandboxService


MAX_TERMINAL_OUTPUT_CHARS = 60_000
TERMINAL_TIMEOUT_SECONDS = 15 * 60
READ_ONLY_GIT_COMMANDS = {"branch", "diff", "log", "rev-parse", "show", "status"}
TerminalStatus = Literal["awaiting_approval", "running", "cancelling", "completed", "failed", "cancelled"]


@dataclass
class TerminalJob:
    job_id: str
    owner_id: str
    workspace_id: str
    project_id: str
    workspace_path: Path
    command: list[str]
    working_directory: str
    status: TerminalStatus = "awaiting_approval"
    output: str = ""
    output_truncated: bool = False
    exit_code: int | None = None
    reason: str | None = None
    cancel_requested: Event = field(default_factory=Event)
    process: subprocess.Popen[str] | None = None
    execution_environment: str = "host"
    sandbox_container_name: str | None = None


class TerminalService:
    _jobs: dict[str, TerminalJob] = {}
    _lock = RLock()

    @classmethod
    def create(
        cls,
        owner_id: str,
        workspace_id: str,
        project_id: str,
        workspace_path: Path,
        command: list[str],
        working_directory: str,
    ) -> dict:
        validated_command = cls._validate_command(command)
        normalized_directory = cls._working_directory(workspace_path, working_directory)

        with cls._lock:
            if any(
                job.owner_id == owner_id
                and job.workspace_id == workspace_id
                and job.status in {"awaiting_approval", "running", "cancelling"}
                for job in cls._jobs.values()
            ):
                raise ValueError("A terminal command is already active in this worktree")

            job = TerminalJob(
                job_id=str(uuid4()),
                owner_id=owner_id,
                workspace_id=workspace_id,
                project_id=project_id,
                workspace_path=workspace_path.resolve(),
                command=validated_command,
                working_directory=normalized_directory,
            )
            cls._jobs[job.job_id] = job
        return cls._serialize(job)

    @classmethod
    def get(cls, job_id: str, owner_id: str, workspace_id: str, project_id: str) -> dict:
        return cls._serialize(cls._job_for_user(job_id, owner_id, workspace_id, project_id))

    @classmethod
    def resume(cls, job_id: str, approve: bool, owner_id: str, workspace_id: str, project_id: str) -> dict:
        job = cls._job_for_user(job_id, owner_id, workspace_id, project_id)
        with cls._lock:
            if job.status != "awaiting_approval":
                raise ValueError("terminal job is not waiting for approval")
            if not approve:
                job.status = "cancelled"
                job.reason = "The command was not approved."
                return cls._serialize(job)
            job.status = "running"
            job.reason = None

        Thread(target=cls._run, args=(job,), daemon=True, name=f"terminal-{job.job_id[:8]}").start()
        return cls._serialize(job)

    @classmethod
    def cancel(cls, job_id: str, owner_id: str, workspace_id: str, project_id: str) -> dict:
        job = cls._job_for_user(job_id, owner_id, workspace_id, project_id)
        with cls._lock:
            if job.status == "awaiting_approval":
                job.status = "cancelled"
                job.reason = "The command was cancelled before approval."
            elif job.status in {"running", "cancelling"}:
                job.cancel_requested.set()
                job.status = "cancelling"
                cls._append_output(job, "\nStopping command…\n")
            else:
                raise ValueError("terminal job is no longer running")
        return cls._serialize(job)

    @classmethod
    def _run(cls, job: TerminalJob) -> None:
        working_path = (job.workspace_path / Path(*PurePosixPath(job.working_directory).parts)).resolve()
        try:
            launch = SandboxService.prepare(job.command, job.workspace_path, job.working_directory, job.job_id.replace("-", ""))
            process = subprocess.Popen(
                launch.command,
                cwd=working_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                shell=False,
            )
        except SandboxError as error:
            with cls._lock:
                job.status = "failed"
                job.reason = str(error)
            return
        except FileNotFoundError:
            with cls._lock:
                job.status = "failed"
                job.reason = f"{job.command[0]} is not installed."
            return
        except OSError as error:
            with cls._lock:
                job.status = "failed"
                job.reason = f"Could not start command: {error}"
            return

        with cls._lock:
            job.process = process
            job.execution_environment = launch.environment
            job.sandbox_container_name = launch.container_name
            cls._append_output(job, f"[{launch.environment}] $ " + " ".join(job.command) + "\n")

        reader = Thread(target=cls._read_output, args=(job, process), daemon=True)
        reader.start()
        started_at = monotonic()
        cancelled = False
        timed_out = False

        while process.poll() is None:
            if job.cancel_requested.is_set():
                cancelled = True
                process.terminate()
                SandboxService.stop(job.sandbox_container_name)
                break
            if monotonic() - started_at > TERMINAL_TIMEOUT_SECONDS:
                timed_out = True
                process.terminate()
                SandboxService.stop(job.sandbox_container_name)
                break
            sleep(0.15)

        try:
            exit_code = process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            exit_code = process.wait(timeout=10)

        reader.join(timeout=2)
        with cls._lock:
            job.process = None
            job.sandbox_container_name = None
            job.exit_code = exit_code
            if cancelled:
                job.status = "cancelled"
                job.reason = "The command was stopped by the user."
            elif timed_out:
                job.status = "failed"
                job.reason = f"The command exceeded the {TERMINAL_TIMEOUT_SECONDS}-second limit."
            elif exit_code == 0:
                job.status = "completed"
            else:
                job.status = "failed"
                job.reason = f"Command exited with code {exit_code}."

    @classmethod
    def _read_output(cls, job: TerminalJob, process: subprocess.Popen[str]) -> None:
        if process.stdout is None:
            return
        try:
            for line in iter(process.stdout.readline, ""):
                with cls._lock:
                    cls._append_output(job, line)
        finally:
            process.stdout.close()

    @classmethod
    def _job_for_user(cls, job_id: str, owner_id: str, workspace_id: str, project_id: str) -> TerminalJob:
        with cls._lock:
            job = cls._jobs.get(job_id)
        if job is None or job.owner_id != owner_id:
            raise KeyError(job_id)
        if job.workspace_id != workspace_id:
            raise ValueError("terminal job belongs to a different worktree")
        if job.project_id != project_id:
            raise ValueError("terminal job belongs to a different project")
        return job

    @staticmethod
    def _validate_command(command: list[str]) -> list[str]:
        if command and command[0].casefold() == "git":
            if len(command) < 2 or command[1].casefold() not in READ_ONLY_GIT_COMMANDS:
                allowed = ", ".join(sorted(READ_ONLY_GIT_COMMANDS))
                raise ValueError(f"terminal Git commands are limited to read-only actions: {allowed}")
            return list(command)
        return validate_project_command(command)

    @staticmethod
    def _working_directory(workspace_path: Path, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("working_directory must be a workspace-relative directory")
        path = PurePosixPath(value.replace("\\", "/"))
        if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts if part != "."):
            raise ValueError("working_directory must stay inside the workspace")
        target = (workspace_path / Path(*path.parts)).resolve()
        root = workspace_path.resolve()
        if target != root and root not in target.parents:
            raise ValueError("working_directory must stay inside the workspace")
        if not target.is_dir():
            raise ValueError("working_directory does not exist")
        return "." if str(path) in {"", "."} else path.as_posix()

    @classmethod
    def _append_output(cls, job: TerminalJob, text: str) -> None:
        job.output += text
        if len(job.output) > MAX_TERMINAL_OUTPUT_CHARS:
            job.output = "… earlier terminal output truncated …\n" + job.output[-MAX_TERMINAL_OUTPUT_CHARS:]
            job.output_truncated = True

    @staticmethod
    def _serialize(job: TerminalJob) -> dict:
        return {
            "job_id": job.job_id,
            "status": job.status,
            "command": job.command,
            "working_directory": job.working_directory,
            "output": job.output,
            "output_truncated": job.output_truncated,
            "exit_code": job.exit_code,
            "reason": job.reason,
            "execution_environment": job.execution_environment,
            "isolated": job.execution_environment == "docker",
        }
