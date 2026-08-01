import sys
import os


sys.path.append(
    os.path.dirname(
        os.path.dirname(__file__)
    )
)


from app.retrieval.code_reader import CodeReader


reader = CodeReader()


code = reader.read_lines(
    "app/services/chat_service.py",
    6,
    15
)


print(code)