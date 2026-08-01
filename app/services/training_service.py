"""Private dataset curation and deterministic evaluation for later adapter training."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import re
from threading import RLock
from uuid import uuid4

from app.agents.ollama_agent import OllamaAgent
from app.core.redaction import redact_text
from app.core.settings import settings
from app.services.auth_service import AuthenticatedUser


class TrainingError(ValueError):
    """Safe data-curation or evaluation error."""


class TrainingService:
    """Store only user-curated, secret-screened examples; never self-train silently."""

    _lock = RLock()
    _tag_pattern = re.compile(r"^[a-z0-9][a-z0-9._-]{0,31}$")
    _export_pattern = re.compile(r"^training-[A-Za-z0-9TZ-]{16,64}\.jsonl$")

    @classmethod
    def overview(cls, user: AuthenticatedUser) -> dict[str, object]:
        with cls._lock:
            examples = cls._load_list(cls._examples_path(user))
            evaluations = cls._load_list(cls._evaluations_path(user))
            history = cls._load_list(cls._history_path(user))
        latest = history[0] if history else None
        return {
            "example_count": len(examples),
            "evaluation_count": len(evaluations),
            "latest_evaluation": latest,
            "training_policy": "manual examples only; secret-shaped text is rejected; no automatic fine-tuning",
        }

    @classmethod
    def add_example(
        cls, user: AuthenticatedUser, instruction: str, ideal_response: str, tags: list[str]
    ) -> dict[str, object]:
        clean_instruction = cls._safe_text(instruction, "instruction", 12_000)
        clean_response = cls._safe_text(ideal_response, "ideal response", 48_000)
        clean_tags = cls._tags(tags)
        record = {
            "id": str(uuid4()),
            "created_at": datetime.now(UTC).isoformat(),
            "instruction": clean_instruction,
            "ideal_response": clean_response,
            "tags": clean_tags,
            "source": "manual-approved",
        }
        with cls._lock:
            examples = cls._load_list(cls._examples_path(user))
            examples.insert(0, record)
            cls._save_list(cls._examples_path(user), examples[:2_000])
        return {"id": record["id"], "example_count": len(examples), "tags": clean_tags}

    @classmethod
    def add_evaluation(
        cls, user: AuthenticatedUser, prompt: str, required_terms: list[str]
    ) -> dict[str, object]:
        clean_prompt = cls._safe_text(prompt, "evaluation prompt", 12_000)
        terms = [cls._safe_text(item, "required term", 200).casefold() for item in required_terms if item.strip()]
        if not terms or len(terms) > 12:
            raise TrainingError("Add 1-12 required terms that identify a correct answer")
        record = {"id": str(uuid4()), "created_at": datetime.now(UTC).isoformat(), "prompt": clean_prompt, "required_terms": terms}
        with cls._lock:
            evaluations = cls._load_list(cls._evaluations_path(user))
            evaluations.insert(0, record)
            cls._save_list(cls._evaluations_path(user), evaluations[:100])
        return {"id": record["id"], "evaluation_count": len(evaluations)}

    @classmethod
    def run_evaluations(cls, user: AuthenticatedUser) -> dict[str, object]:
        with cls._lock:
            evaluations = cls._load_list(cls._evaluations_path(user))[:20]
        if not evaluations:
            raise TrainingError("Add at least one evaluation before running a benchmark")
        results: list[dict[str, object]] = []
        for evaluation in evaluations:
            answer = OllamaAgent.ask(
                [
                    {"role": "system", "content": "Answer the coding task accurately and concisely. Do not claim actions you cannot perform."},
                    {"role": "user", "content": evaluation["prompt"]},
                ]
            )
            lowered = answer.casefold()
            matched = [term for term in evaluation["required_terms"] if term in lowered]
            results.append({"id": evaluation["id"], "passed": len(matched) == len(evaluation["required_terms"]), "matched_terms": len(matched), "required_terms": len(evaluation["required_terms"])})
        passed = sum(1 for result in results if result["passed"])
        report = {
            "created_at": datetime.now(UTC).isoformat(),
            "total": len(results),
            "passed": passed,
            "score_percent": round((passed / len(results)) * 100, 1),
            "results": results,
        }
        with cls._lock:
            history = cls._load_list(cls._history_path(user))
            history.insert(0, report)
            cls._save_list(cls._history_path(user), history[:100])
        return report

    @classmethod
    def export_jsonl(cls, user: AuthenticatedUser) -> dict[str, object]:
        with cls._lock:
            examples = list(reversed(cls._load_list(cls._examples_path(user))))
        if not examples:
            raise TrainingError("Add at least one approved example before exporting a dataset")
        name = f"training-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}.jsonl"
        path = cls._exports_directory(user) / name
        lines = []
        for example in examples:
            lines.append(
                json.dumps(
                    {
                        "messages": [
                            {"role": "system", "content": "You are a careful coding assistant. Explain assumptions, preserve safety boundaries, and verify work."},
                            {"role": "user", "content": example["instruction"]},
                            {"role": "assistant", "content": example["ideal_response"]},
                        ],
                        "metadata": {"example_id": example["id"], "tags": example["tags"], "source": "manual-approved"},
                    },
                    ensure_ascii=False,
                )
            )
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        except OSError as error:
            raise TrainingError("Could not write the training export") from error
        return {"file_name": name, "example_count": len(examples), "format": "chat-jsonl"}

    @classmethod
    def export_path(cls, user: AuthenticatedUser, file_name: str) -> Path:
        if not cls._export_pattern.fullmatch(file_name):
            raise TrainingError("Training export name is invalid")
        path = (cls._exports_directory(user) / file_name).resolve()
        root = cls._exports_directory(user).resolve()
        if root not in path.parents or not path.is_file():
            raise TrainingError("Training export is not available")
        return path

    @classmethod
    def _safe_text(cls, value: str, label: str, maximum: int) -> str:
        if not isinstance(value, str) or not value.strip() or len(value) > maximum:
            raise TrainingError(f"{label} must contain 1-{maximum} characters")
        stripped = value.strip()
        if redact_text(stripped) != stripped:
            raise TrainingError(f"{label} looks like it contains a credential. Remove it before saving training data")
        return stripped

    @classmethod
    def _tags(cls, tags: list[str]) -> list[str]:
        normalized: list[str] = []
        for tag in tags:
            candidate = str(tag).strip().casefold()
            if not candidate:
                continue
            if not cls._tag_pattern.fullmatch(candidate):
                raise TrainingError("Tags use lowercase letters, digits, dots, dashes, or underscores only")
            if candidate not in normalized:
                normalized.append(candidate)
        if len(normalized) > 8:
            raise TrainingError("Use at most 8 tags")
        return normalized

    @staticmethod
    def _load_list(path: Path) -> list[dict]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            return value if isinstance(value, list) else []
        except (OSError, ValueError, json.JSONDecodeError):
            return []

    @staticmethod
    def _save_list(path: Path, value: list[dict]) -> None:
        temporary = path.with_suffix(".tmp")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
            temporary.replace(path)
        except OSError as error:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            raise TrainingError("Could not save training data") from error

    @staticmethod
    def _training_root(user: AuthenticatedUser) -> Path:
        return Path(settings.agent_state_root).expanduser().resolve().parent / "training" / user.id

    @classmethod
    def _examples_path(cls, user: AuthenticatedUser) -> Path:
        return cls._training_root(user) / "examples.json"

    @classmethod
    def _evaluations_path(cls, user: AuthenticatedUser) -> Path:
        return cls._training_root(user) / "evaluations.json"

    @classmethod
    def _history_path(cls, user: AuthenticatedUser) -> Path:
        return cls._training_root(user) / "evaluation-history.json"

    @classmethod
    def _exports_directory(cls, user: AuthenticatedUser) -> Path:
        return cls._training_root(user) / "exports"
