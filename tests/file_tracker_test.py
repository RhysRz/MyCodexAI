import sys
import os

sys.path.append(
    os.path.dirname(
        os.path.dirname(__file__)
    )
)


from app.index.file_tracker import FileTracker


tracker = FileTracker()


info = tracker.get_file_info(
    "app/services/chat_service.py"
)


print(info)