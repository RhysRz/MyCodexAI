from app.index.symbol_index import SymbolIndexer
from app.index.index_store import IndexStore
from app.index.file_tracker import FileTracker


class ProjectIndexer:


    def __init__(self):

        self.symbol_indexer = SymbolIndexer()
        self.store = IndexStore()
        self.tracker = FileTracker()



    def build(self, files):

        index = {
            "files": []
        }


        for file in files:


            # วิเคราะห์เฉพาะ Python file

            if not file.endswith(".py"):
                continue



            symbols = self.symbol_indexer.index_file(
                file
            )


            file_info = self.tracker.get_file_info(
                file
            )


            index["files"].append({

                "path": file_info["path"],

                "modified": file_info["modified"],

                "symbols": symbols

            })


        self.store.save(
            index
        )


        return index