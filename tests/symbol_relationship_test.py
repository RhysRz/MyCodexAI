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
from app.graph.call_graph_builder import CallGraphBuilder
from app.graph.symbol_relationship import SymbolRelationshipResolver



symbol_builder = SymbolGraphBuilder()

call_builder = CallGraphBuilder()



symbol_graph = symbol_builder.build(
    "app"
)


call_graph = call_builder.build(
    "app"
)



resolver = SymbolRelationshipResolver()


result = resolver.build(
    symbol_graph,
    call_graph
)



for name, data in result.items():

    print("\nCLASS:", name)


    for method in data["methods"]:

        print(
            " METHOD:",
            method["name"]
        )

        print(
            " CALLS:",
            method["calls"]
        )