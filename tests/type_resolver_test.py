import sys
import os


sys.path.append(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)


from app.graph.unified_graph_builder import UnifiedGraphBuilder
from app.graph.graph_type_resolver import GraphTypeResolver



builder = UnifiedGraphBuilder()


graph = builder.build(
    "app"
)


resolver = GraphTypeResolver()


graph = resolver.resolve(
    graph
)



print(
    graph.get_all().get(
        "ChatService"
    )
)


print(
    graph.get_all().get(
        "chat"
    )
)