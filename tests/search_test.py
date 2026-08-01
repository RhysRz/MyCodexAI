import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.workspace.search import CodeSearch

files = CodeSearch.search("ToolPlanner")

print(files)