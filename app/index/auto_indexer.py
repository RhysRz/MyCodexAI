from app.index.project_indexer import ProjectIndexer
from app.workspace.scanner import WorkspaceScanner


class AutoIndexer:

    def __init__(self):

        self.scanner = WorkspaceScanner()
        self.project_indexer = ProjectIndexer()


    def build_project(self, root):

        files = self.scanner.scan(root)

        python_files = [
            file
            for file in files
            if file.endswith(".py")
        ]


        return self.project_indexer.build(
            python_files
        )