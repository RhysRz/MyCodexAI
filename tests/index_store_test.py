import sys
import os

sys.path.append(
    os.path.dirname(
        os.path.dirname(__file__)
    )
)

from app.index.index_store import IndexStore


store = IndexStore()


data = {
    "files": [
        {
            "path": "app/services/chat_service.py",
            "symbols": [
                {
                    "type": "class",
                    "name": "ChatService"
                }
            ]
        }
    ]
}


store.save(data)


result = store.load()


print(result)