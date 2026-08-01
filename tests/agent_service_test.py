import json
from pathlib import Path
from tempfile import TemporaryDirectory

from app.agents.ollama_agent import OllamaAgent
from app.agents.agent_protocol import AgentProtocol
from app.services.agent_service import AgentService
from app.tools.agent_tools import AGENT_TOOLS, AgentToolExecutor


temporary_state = TemporaryDirectory()
original_state_root = AgentService._state_root
AgentService._state_root = Path(temporary_state.name).resolve()


responses = iter(
    [
        json.dumps(
            {
                "action": {
                    "tool": "read_file",
                    "arguments": {"filename": "hello.txt"},
                },
                "summary": "Inspect the current workspace file first.",
            }
        ),
        json.dumps(
            {
                "action": {
                    "tool": "write_file",
                    "arguments": {
                        "filename": "hello.txt",
                        "content": "updated by agent\n",
                    },
                },
                "summary": "Apply the requested change.",
            }
        ),
        json.dumps(
            {
                "action": {
                    "tool": "final",
                    "arguments": {"answer": "Updated hello.txt."},
                },
                "summary": "",
            }
        ),
    ]
)

original_ask = OllamaAgent.ask
original_ask_json = OllamaAgent.ask_json
original_write = AGENT_TOOLS["write_file"].function

OllamaAgent.ask = classmethod(lambda _cls, _messages: next(responses))
OllamaAgent.ask_json = classmethod(lambda _cls, _messages: next(responses))
AGENT_TOOLS["write_file"].function = lambda filename, content: {
    "status": "written",
    "filename": filename,
    "characters_written": len(content),
}

try:
    AgentService._runs.clear()
    run = AgentService.start("Update hello.txt")

    assert run["status"] == "awaiting_approval"
    assert run["pending_action"]["tool"] == "write_file"
    assert "updated by agent" in run["pending_action"]["preview"]["diff"]

    completed = AgentService.resume(run["run_id"], approve=True)
    assert completed["status"] == "completed"
    assert completed["answer"] == "Updated hello.txt."
    assert any(item["status"] == "written" for item in completed["trace"])

    preview = AgentToolExecutor.preview(
        "write_file",
        {"filename": "hello.txt", "content": "\nkeeps whitespace\n"},
    )
    assert "keeps whitespace" in preview["diff"]
finally:
    OllamaAgent.ask = original_ask
    OllamaAgent.ask_json = original_ask_json
    AGENT_TOOLS["write_file"].function = original_write


batch_responses = iter(
    [
        json.dumps(
            {
                "action": {
                    "tool": "write_files",
                    "arguments": {
                        "files": [
                            {"filename": "build/index.html", "content": "<h1>My app</h1>\n"},
                            {"filename": "build/app.js", "content": "console.log('ready');\n"},
                        ]
                    },
                },
                "summary": "Create the related starter files in one review.",
            }
        ),
        json.dumps(
            {
                "action": {
                    "tool": "final",
                    "arguments": {"answer": "Created the starter files."},
                },
                "summary": "",
            }
        ),
    ]
)
original_batch_write = AGENT_TOOLS["write_files"].function
OllamaAgent.ask_json = classmethod(lambda _cls, _messages: next(batch_responses))
AGENT_TOOLS["write_files"].function = lambda files: {
    "status": "written",
    "file_count": len(files),
    "files": [file["filename"] for file in files],
    "characters_written": sum(len(file["content"]) for file in files),
}

try:
    AgentService._runs.clear()
    run = AgentService.start("Create a small starter app")

    assert run["status"] == "awaiting_approval"
    assert run["pending_action"]["tool"] == "write_files"
    assert run["pending_action"]["preview"]["file_count"] == 2
    assert "build/index.html" in run["pending_action"]["preview"]["diff"]
    assert "build/app.js" in run["pending_action"]["preview"]["diff"]

    completed = AgentService.resume(run["run_id"], approve=True)
    assert completed["status"] == "completed"
    assert completed["answer"] == "Created the starter files."
    assert any(item["tool"] == "write_files" and item["status"] == "written" for item in completed["trace"])

    try:
        AgentToolExecutor.preview(
            "write_files",
            {
                "files": [
                    {"filename": "duplicate.txt", "content": "one"},
                    {"filename": "DUPLICATE.txt", "content": "two"},
                ]
            },
        )
        raise AssertionError("duplicate batch paths should be rejected")
    except ValueError as error:
        assert "duplicate path" in str(error)
finally:
    OllamaAgent.ask_json = original_ask_json
    AGENT_TOOLS["write_files"].function = original_batch_write


project_responses = iter(
    [
        json.dumps(
            {
                "action": {
                    "tool": "set_project_plan",
                    "arguments": {
                        "name": "Sample project",
                        "overview": "A small local starter application.",
                        "milestones": ["Create the starter files", "Run verification"],
                    },
                },
                "summary": "Record the build plan before creating files.",
            }
        ),
        json.dumps(
            {
                "action": {
                    "tool": "write_files",
                    "arguments": {
                        "files": [
                            {"filename": "sample/README.md", "content": "# Sample\n"},
                            {"filename": "sample/app.js", "content": "console.log('sample');\n"},
                        ]
                    },
                },
                "summary": "Create the first reviewed project batch.",
            }
        ),
        json.dumps(
            {
                "action": {
                    "tool": "final",
                    "arguments": {"answer": "The sample project is ready."},
                },
                "summary": "",
            }
        ),
    ]
)
original_project_write = AGENT_TOOLS["write_files"].function
OllamaAgent.ask_json = classmethod(lambda _cls, _messages: next(project_responses))
AGENT_TOOLS["write_files"].function = lambda files: {
    "status": "written",
    "file_count": len(files),
    "files": [file["filename"] for file in files],
    "characters_written": sum(len(file["content"]) for file in files),
}

try:
    AgentService._runs.clear()
    run = AgentService.start("Build a sample project", mode="project")

    assert run["mode"] == "project"
    assert run["status"] == "awaiting_approval"
    assert run["project_plan"]["name"] == "Sample project"
    assert run["progress"]["max_steps"] == 60
    assert run["trace"][0]["tool"] == "set_project_plan"

    completed = AgentService.resume(run["run_id"], approve=True)
    assert completed["status"] == "completed"
    assert completed["answer"] == "The sample project is ready."

    AgentService._runs.clear()
    restored = AgentService.get(completed["run_id"])
    assert restored["project_plan"]["name"] == "Sample project"
    assert restored["status"] == "completed"

    command_preview = AgentToolExecutor.preview(
        "run_project_command",
        {"command": ["npm", "test"]},
    )
    assert command_preview["status"] == "preview"
    assert "npm test" in command_preview["diff"]
finally:
    OllamaAgent.ask_json = original_ask_json
    AGENT_TOOLS["write_files"].function = original_project_write


git_responses = iter(
    [
        json.dumps(
            {
                "action": {"tool": "git_initialize", "arguments": {"branch": "main"}},
                "summary": "Initialize version control before the project work.",
            }
        ),
        json.dumps(
            {
                "action": {"tool": "git_commit", "arguments": {"message": "Create starter project"}},
                "summary": "Save the reviewed project checkpoint.",
            }
        ),
        json.dumps(
            {
                "action": {"tool": "final", "arguments": {"answer": "Created a Git checkpoint."}},
                "summary": "",
            }
        ),
    ]
)
original_git_initialize = AGENT_TOOLS["git_initialize"].function
original_git_commit = AGENT_TOOLS["git_commit"].function
OllamaAgent.ask_json = classmethod(lambda _cls, _messages: next(git_responses))
AGENT_TOOLS["git_initialize"].function = lambda branch="main": {"status": "ok", "branch": branch}
AGENT_TOOLS["git_commit"].function = lambda message: {"status": "ok", "message": message}

try:
    AgentService._runs.clear()
    run = AgentService.start("Build a versioned starter project", mode="project")
    assert run["status"] == "awaiting_approval"
    assert run["pending_action"]["tool"] == "git_initialize"

    checkpoint = AgentService.resume(run["run_id"], approve=True)
    assert checkpoint["status"] == "awaiting_approval"
    assert checkpoint["pending_action"]["tool"] == "git_commit"

    completed = AgentService.resume(run["run_id"], approve=True)
    assert completed["status"] == "completed"
    assert completed["answer"] == "Created a Git checkpoint."
finally:
    OllamaAgent.ask_json = original_ask_json
    AGENT_TOOLS["git_initialize"].function = original_git_initialize
    AGENT_TOOLS["git_commit"].function = original_git_commit
    AgentService._state_root = original_state_root
    temporary_state.cleanup()

assert AgentProtocol.parse('note before {"action":{"tool":"final","arguments":{"answer":"ok"}}}') == {
    "tool": "final",
    "arguments": {"answer": "ok"},
    "summary": "",
}

print("agent_service=ok")
