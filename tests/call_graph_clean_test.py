import sys
import os


sys.path.append(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)


from app.graph.call_graph_builder import CallGraphBuilder
from app.graph.call_graph_cleaner import CallGraphCleaner



builder = CallGraphBuilder()


graph = builder.build_file_graph(
    "app/services/chat_service.py"
)


cleaner = CallGraphCleaner()


graph = cleaner.clean(
    graph
)


print(graph.get_all())