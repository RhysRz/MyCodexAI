import sys
import os


sys.path.append(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)


from app.graph.unified_graph import UnifiedCodeGraph
from app.graph.code_graph import CodeGraph



project_graph = CodeGraph()

project_graph.add_node(
    "ChatService",
    "class"
)

project_graph.add_edge(
    "ChatService",
    "IntentRouter",
    "class",
    "class"
)



symbol_graph = CodeGraph()

symbol_graph.add_node(
    "ChatService",
    "class"
)

symbol_graph.add_edge(
    "ChatService",
    "chat",
    "class",
    "method"
)



call_graph = CodeGraph()

call_graph.add_node(
    "chat",
    "method"
)

call_graph.add_edge(
    "chat",
    "IntentRouter.handle",
    "method",
    "call"
)



unified = UnifiedCodeGraph()


graph = unified.merge(
    [
        project_graph,
        symbol_graph,
        call_graph
    ]
)



print(
    "========== UNIFIED GRAPH =========="
)


print(
    graph.get_all()
)


print(
    "========== CONTEXT =========="
)


print(
    unified.get_context(
        "ChatService"
    )
)