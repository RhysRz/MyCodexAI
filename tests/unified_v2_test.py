# -*- coding: utf-8 -*-

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(
    0,
    str(ROOT)
)


from app.graph.unified_graph_builder import UnifiedGraphBuilder



print(
    "========== UNIFIED GRAPH V2 =========="
)


builder = UnifiedGraphBuilder()


graph = builder.build(
    "app"
)



print(
    graph.stats()
)



print(
    "\n========== CHAT SERVICE =========="
)


print(
    graph.get_node(
        "ChatService"
    )
)



print(
    "\n========== EDGES =========="
)


for edge in graph.get_dependencies(
    "ChatService"
):

    print(edge)