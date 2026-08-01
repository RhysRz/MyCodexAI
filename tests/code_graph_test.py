import sys
import os


sys.path.append(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)


from app.graph.code_graph import CodeGraph



graph = CodeGraph()



graph.add_edge(
    "ChatService",
    "IntentRouter"
)


graph.add_edge(
    "ChatService",
    "SessionMemory"
)


graph.add_edge(
    "ChatService",
    "ContextBuilder"
)



print(
    graph.get_all()
)


print(
    graph.get_dependencies(
        "ChatService"
    )
)