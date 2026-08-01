"""Verify the private training controls are wired into the workspace UI."""

from pathlib import Path


root = Path(__file__).resolve().parent.parent
index = (root / "templates" / "index.html").read_text(encoding="utf-8")
script = (root / "static" / "script.js").read_text(encoding="utf-8")

for identifier in (
    "learning-status",
    "learning-instruction",
    "learning-ideal-response",
    "save-learning-example",
    "learning-eval-prompt",
    "save-learning-eval",
    "run-learning-evals",
    "export-learning-jsonl",
):
    assert f'id="{identifier}"' in index

for function_name in (
    "loadLearning",
    "saveLearningExample",
    "saveLearningEvaluation",
    "runLearningEvaluations",
    "exportLearningJsonl",
):
    assert f"function {function_name}" in script

assert "/api/learning/overview" in script
assert "/api/learning/exports" in script
print("training_ui=ok")
