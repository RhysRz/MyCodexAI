import sys
import os

sys.path.append(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)


from app.memory.session import SessionMemory



memory = SessionMemory()


memory.add_user(
    "เปิด chat_service.py"
)


memory.add_assistant(
    "นี่คือไฟล์ ChatService"
)


print(
    memory.get()
)