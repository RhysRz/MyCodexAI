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



builder = UnifiedGraphBuilder()


graph = builder.build(
    "app"
)


print(
    "========== FULL UNIFIED GRAPH =========="
)


for node, data in graph.get_all().items():

    print(
        node,
        "=>",
        data
    )