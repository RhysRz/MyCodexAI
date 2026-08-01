import sys
import os

sys.path.append(
    os.path.dirname(
        os.path.dirname(__file__)
    )
)

from app.index.symbol_index import SymbolIndexer


indexer = SymbolIndexer()


result = indexer.index_file(
    "app/services/chat_service.py"
)


print(result)