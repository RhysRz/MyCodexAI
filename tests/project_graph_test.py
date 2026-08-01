import sys
import os


sys.path.append(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)


from app.graph.project_graph_builder import ProjectGraphBuilder



builder = ProjectGraphBuilder()



graph = builder.build(
    "app"
)



print(
    "\n========== RAW GRAPH ==========\n"
)


for key, value in graph.get_all().items():

    print(
        key,
        "=>",
        value
    )



print(
    "\n========== CLEAN GRAPH ==========\n"
)


graph.clean_external()



for key, value in graph.get_all().items():

    print(
        key,
        "=>",
        value
    )