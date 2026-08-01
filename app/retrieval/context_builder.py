from app.retrieval.symbol_retriever import SymbolRetriever
from app.retrieval.code_reader import CodeReader


class ContextBuilder:


    def __init__(self):

        self.retriever = SymbolRetriever()
        self.reader = CodeReader()



    def build(self, keyword):

        results = self.retriever.search(
            keyword
        )


        contexts = []


        for item in results:

            symbol = item["symbol"]

            code = self.reader.read_lines(
                item["file"],
                symbol["line_start"],
                symbol["line_end"]
            )


            contexts.append({

                "file": item["file"],

                "symbol": symbol["name"],

                "code": code

            })


        return contexts