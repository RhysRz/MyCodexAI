import sys
import os


sys.path.append(
    os.path.dirname(
        os.path.dirname(__file__)
    )
)


from app.services.prompt_builder import PromptBuilder


builder = PromptBuilder()


context = [
    {
        "file": "app/services/chat_service.py",
        "symbol": "ChatService",
        "code": "class ChatService:"
    }
]


result = builder.build(
    context,
    "แก้ระบบ Chat ให้หน่อย"
)


print(result)