import sys
from pathlib import Path
import inspect


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(
    0,
    str(ROOT)
)


from app.graph.unified_graph_builder import UnifiedGraphBuilder
from app.graph.symbol_relationship_resolver import SymbolRelationshipResolver



print(
    "LOADED:",
    inspect.getfile(SymbolRelationshipResolver)
)

print(
    "SIGNATURE:",
    inspect.signature(
        SymbolRelationshipResolver.__init__
    )
)



print(
    "========== ADVANCED RELATIONSHIPS =========="
)



builder = UnifiedGraphBuilder()


graph = builder.build(
    "app"
)



print(
    "\n========== GRAPH CHECK =========="
)



total_edges = 0


for name, data in graph.get_all().items():


    edges = data.get(
        "edges",
        []
    )


    if edges:


        print(
            "NODE:",
            name
        )


        print(
            "TYPE:",
            data.get(
                "type"
            )
        )


        print(
            "EDGES:",
            edges[:5]
        )


        total_edges += len(
            edges
        )



print(
    "TOTAL NODES:",
    len(
        graph.get_all()
    )
)


print(
    "TOTAL EDGES:",
    total_edges
)


print(
    "=================================\n"
)



resolver = SymbolRelationshipResolver(
    graph
)


relationships = resolver.build()



print(
    "========== RESOLVED RELATIONSHIPS =========="
)



for item in relationships:

    print(
        item
    )