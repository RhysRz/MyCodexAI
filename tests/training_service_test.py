"""Exercise private training-set curation without calling a real model."""

from pathlib import Path
from tempfile import TemporaryDirectory

from app.agents.ollama_agent import OllamaAgent
from app.core.settings import settings
from app.services.auth_service import AuthenticatedUser
from app.services.training_service import TrainingError, TrainingService


temporary_root = TemporaryDirectory()
original_state_root = settings.agent_state_root
original_ask = OllamaAgent.__dict__["ask"]

try:
    root = Path(temporary_root.name)
    settings.agent_state_root = str(root / "state" / "runs")
    user = AuthenticatedUser("training-test-user", "trainer", "user")

    example = TrainingService.add_example(
        user,
        "Explain how to test a FastAPI route.",
        "Use TestClient, call the route, and assert the response status and body.",
        ["FastAPI", "testing"],
    )
    assert example["example_count"] == 1
    assert example["tags"] == ["fastapi", "testing"]

    try:
        TrainingService.add_example(user, "api_key=abcdefghijk", "Do not save this.", [])
        raise AssertionError("credential-shaped training data must be rejected")
    except TrainingError:
        pass

    evaluation = TrainingService.add_evaluation(
        user,
        "How should I test a FastAPI route?",
        ["fastapi", "testclient"],
    )
    assert evaluation["evaluation_count"] == 1

    OllamaAgent.ask = classmethod(lambda cls, messages: "Use FastAPI with TestClient for the route test.")
    report = TrainingService.run_evaluations(user)
    assert report["score_percent"] == 100.0
    assert report["passed"] == 1
    assert "answer" not in report["results"][0]

    exported = TrainingService.export_jsonl(user)
    export_path = TrainingService.export_path(user, str(exported["file_name"]))
    data = export_path.read_text(encoding="utf-8")
    assert '"manual-approved"' in data
    assert "Explain how to test a FastAPI route." in data
finally:
    OllamaAgent.ask = original_ask
    settings.agent_state_root = original_state_root
    temporary_root.cleanup()

print("training_service=ok")
