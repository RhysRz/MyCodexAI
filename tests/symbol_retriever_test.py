import sys
import os


sys.path.append(
    os.path.dirname(
        os.path.dirname(__file__)
    )
)


from app.retrieval.symbol_retriever import SymbolRetriever


retriever = SymbolRetriever()


result = retriever.search(
    "ChatService"
)


print(result)