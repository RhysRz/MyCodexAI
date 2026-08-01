import sys
import os


sys.path.append(
    os.path.dirname(
        os.path.dirname(__file__)
    )
)


from app.retrieval.context_builder import ContextBuilder


builder = ContextBuilder()


result = builder.build(
    "ChatService"
)


print(result)