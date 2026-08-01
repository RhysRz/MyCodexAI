import sys
import os

sys.path.append(
    os.path.dirname(
        os.path.dirname(__file__)
    )
)


from app.index.incremental_indexer import IncrementalIndexer


indexer = IncrementalIndexer()


result = indexer.build(
    [
        "app/services/chat_service.py"
    ]
)


print(result)