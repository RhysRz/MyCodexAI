from app.tools.registry import list_tools

import app.tools.file_tools


for tool in list_tools():

    print()

    print(tool.name)

    print(tool.description)

    print(tool.parameters)