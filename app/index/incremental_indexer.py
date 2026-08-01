from app.index.symbol_index import SymbolIndexer
from app.index.index_store import IndexStore
from app.index.file_tracker import FileTracker
from app.index.change_detector import ChangeDetector


class IncrementalIndexer:


    def __init__(self):

        self.symbol_indexer = SymbolIndexer()
        self.store = IndexStore()
        self.tracker = FileTracker()
        self.detector = ChangeDetector()



    def build(self, files):

        old_index = self.store.load()


        if old_index is None:
            old_index = {
                "files": []
            }


        new_index = {
            "files": []
        }


        for file in files:

            current = self.tracker.get_file_info(file)

            old_file = self.find_old_file(
                old_index,
                file
            )


            if self.detector.is_changed(
                old_file,
                current
            ):

                symbols = self.symbol_indexer.index_file(file)

            else:

                symbols = old_file["symbols"]



            new_index["files"].append({

                "path": file,

                "modified": current["modified"],

                "symbols": symbols

            })


        self.store.save(new_index)


        return new_index



    def find_old_file(
        self,
        index,
        filepath
    ):

        for file in index["files"]:

            if file["path"] == filepath:
                return file


        return None