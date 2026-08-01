# -*- coding: utf-8 -*-

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(
    0,
    str(ROOT)
)


from app.graph.call_graph_builder import CallGraphBuilder



print(
    "========== CALL GRAPH V2 =========="
)


builder = CallGraphBuilder()


graph = builder.build(
    "app"
)


print(
    graph.stats()
)



print(
    "\n========== CHAT SERVICE CALLS =========="
)


for edge in graph.get_dependencies(
    "ChatService"
):

    print(edge)