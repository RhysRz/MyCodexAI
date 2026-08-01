import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from time import sleep

from app.agents.ollama_agent import OllamaAgent
from app.services.agent_service import AgentService
from app.tools.agent_tools import AGENT_TOOLS
from app.workspace.file_manager import FileManager


def wait_for(predicate, message: str) -> None:
    for _ in range(150):
        if predicate():
            return
        sleep(0.02)
    raise AssertionError(message)


temporary_root = TemporaryDirectory()
workspace = Path(temporary_root.name) / "project"
workspace.mkdir()
token = FileManager.activate_workspace(workspace)
original_state_root = AgentService._state_root
original_ask_json = OllamaAgent.ask_json
original_write = AGENT_TOOLS["write_file"].function
AgentService._state_root = Path(temporary_root.name) / "runs"

try:
    AgentService._runs.clear()
    AgentService._background_queue.clear()
    AgentService._queued_background_runs.clear()
    AgentService._background_workers.clear()
    first_started = Event()
    release_first = Event()

    def slow_final(_cls, _messages):
        first_started.set()
        assert release_first.wait(3)
        return json.dumps({"action": {"tool": "final", "arguments": {"answer": "First completed."}}, "summary": ""})

    OllamaAgent.ask_json = classmethod(slow_final)
    first = AgentService.start("First background run", background=True)
    assert first["background"] is True
    assert first_started.wait(1)

    second = AgentService.start("Second background run", background=True)
    waiting = AgentService.get(second["run_id"])
    assert waiting["status"] == "queued"
    assert waiting["progress"]["queue_position"] == 1
    assert waiting["progress"]["queue_total"] == 2

    third = AgentService.start("Third background run", background=True)
    waiting_third = AgentService.get(third["run_id"])
    assert waiting_third["status"] == "queued"
    assert waiting_third["progress"]["queue_position"] == 2
    assert waiting_third["progress"]["queue_total"] == 3
    cancelled = AgentService.cancel(second["run_id"])
    assert cancelled["status"] == "cancelled"
    assert AgentService.get(third["run_id"])["progress"]["queue_position"] == 1
    assert AgentService.cancel(third["run_id"])["status"] == "cancelled"

    release_first.set()
    wait_for(lambda: AgentService.get(first["run_id"])["status"] == "completed", "first run did not complete")

    responses = iter(
        [
            json.dumps(
                {
                    "action": {"tool": "write_file", "arguments": {"filename": "app.txt", "content": "updated\n"}},
                    "summary": "Apply the focused update.",
                }
            ),
            json.dumps(
                {
                    "action": {"tool": "final", "arguments": {"answer": "Approved update completed."}},
                    "summary": "",
                }
            ),
        ]
    )
    OllamaAgent.ask_json = classmethod(lambda _cls, _messages: next(responses))
    AGENT_TOOLS["write_file"].function = lambda filename, content: {
        "status": "written",
        "filename": filename,
        "characters_written": len(content),
    }

    approval = AgentService.start("Update one file", background=True)
    wait_for(
        lambda: AgentService.get(approval["run_id"])["status"] == "awaiting_approval",
        "background run did not request approval",
    )
    resumed = AgentService.resume(approval["run_id"], approve=True)
    assert resumed["status"] in {"queued", "running"}
    wait_for(
        lambda: AgentService.get(approval["run_id"])["status"] == "completed",
        "approved background run did not complete",
    )
finally:
    OllamaAgent.ask_json = original_ask_json
    AGENT_TOOLS["write_file"].function = original_write
    AgentService._state_root = original_state_root
    AgentService._background_queue.clear()
    AgentService._queued_background_runs.clear()
    AgentService._background_workers.clear()
    FileManager.reset_workspace(token)
    temporary_root.cleanup()

print("background_agent=ok")
