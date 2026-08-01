"""Check visible resource-wait progress and compact model-facing tool context."""

from app.services.agent_service import AgentRun, AgentService, MAX_MODEL_TOOL_RESULT_CHARS


large_result = {
    "status": "ok",
    "files": [f"very/deep/path/{index:03d}/source_file_with_a_long_name.py" for index in range(100)],
    "output": "x" * 10_000,
}
compact = AgentService._result_for_model(large_result)
assert any(key.endswith("_truncated_for_model") for key in compact)
assert len(__import__("json").dumps(compact, ensure_ascii=False)) <= MAX_MODEL_TOOL_RESULT_CHARS

run = AgentRun(run_id="run", task="task", max_steps=1, messages=[])
run.activity = {"state": "waiting_for_memory", "message": "Waiting"}
payload = AgentService._serialize(run)
assert payload["activity"]["state"] == "waiting_for_memory"
assert AgentService._tool_activity_message("read_file").startswith("กำลังอ่านไฟล์")
assert "summary` and final answer in natural Thai" in AgentService._system_prompt("agent")

print("agent_progress_context=ok")
