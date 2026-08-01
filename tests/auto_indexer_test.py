import sys
import os

sys.path.append(
    os.path.dirname(
        os.path.dirname(__file__)
    )
)


from app.index.auto_indexer import AutoIndexer


indexer = AutoIndexer()


result = indexer.build_project(
    "."
)


print(result)