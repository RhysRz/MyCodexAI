import sys
import os


sys.path.append(
    os.path.dirname(
        os.path.dirname(__file__)
    )
)


from app.workspace.scanner import WorkspaceScanner
from app.index.project_indexer import ProjectIndexer


scanner = WorkspaceScanner()


files = scanner.scan(
    "."
)


indexer = ProjectIndexer()


result = indexer.build(
    files
)


print(result)