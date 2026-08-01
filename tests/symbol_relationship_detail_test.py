import sys
import os

sys.path.append(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)


from app.graph.symbol_graph_builder import SymbolGraphBuilder
from app.graph.symbol_relationship_resolver import SymbolRelationshipResolver


builder = SymbolGraphBuilder()

graph = builder.build(
    "app"
)


resolver = SymbolRelationshipResolver(
    graph
)


result = resolver.resolve()


print(
    "========== SYMBOL RELATIONSHIPS =========="
)


for item in result:

    if item["type"] != "references":
        print(item)