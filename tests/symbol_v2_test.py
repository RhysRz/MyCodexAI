# -*- coding: utf-8 -*-

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(
    0,
    str(ROOT)
)


from app.graph.symbol_graph_builder import SymbolGraphBuilder



print("========== SYMBOL GRAPH V2 ==========")


builder = SymbolGraphBuilder()


graph = builder.build(
    "app"
)



print(
    "STATS:",
    graph.stats()
)



print("\n========== CHAT SERVICE ==========")


print(
    graph.get_node(
        "ChatService"
    )
)



print("\n========== DEPENDENCIES ==========")


for edge in graph.get_dependencies(
    "ChatService"
):

    print(edge)