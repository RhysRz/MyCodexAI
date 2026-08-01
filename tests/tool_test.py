from app.tools.executor import ToolExecutor

print(ToolExecutor.execute("list_files"))

print(ToolExecutor.execute(
    "read_file",
    filename="hello.txt"
))