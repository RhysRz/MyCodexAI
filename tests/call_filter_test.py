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
from app.graph.call_graph_filter import CallGraphFilter



builder = UnifiedGraphBuilder()


graph = builder.build(
    "app"
)


cleaner = CallGraphFilter()


graph = cleaner.clean(
    graph
)



for node, data in graph.get_all().items():

    if node in [
        "ChatService",
        "chat"
    ]:

        print(
            node,
            "=>",
            data
        )