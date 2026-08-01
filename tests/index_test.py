from app.workspace.project_index import ProjectIndex

index = ProjectIndex.build()

for filename, info in index.items():

    print()

    print(filename)

    print(info)