import sys
import os

sys.path.append(
    os.path.abspath(
        "."
    )
)


from app.graph.unified_graph_builder import UnifiedGraphBuilder



builder = UnifiedGraphBuilder()


graph = builder.build(
    "app"
)



for node, data in graph.get_all().items():

    print(
        node,
        "=>",
        data
    )