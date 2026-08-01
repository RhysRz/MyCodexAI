import sys
import os


sys.path.append(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)


from app.graph.import_graph_builder import ImportGraphBuilder



builder = ImportGraphBuilder()



graph = builder.build_file_graph(
    "app/services/chat_service.py"
)



print(
    graph.get_all()
)