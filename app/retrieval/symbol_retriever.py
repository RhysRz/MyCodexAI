from app.index.index_store import IndexStore


class SymbolRetriever:


    def __init__(self):

        self.store = IndexStore()



    def search(self, keyword):

        index = self.store.load()


        if index is None:
            return []


        results = []


        words = keyword.lower().split()


        for file in index["files"]:

            for symbol in file["symbols"]:


                name = symbol["name"].lower()


                for word in words:

                    if word in name:

                        results.append(
                            {
                                "file": file["path"],
                                "symbol": symbol
                            }
                        )

                        break


        return results