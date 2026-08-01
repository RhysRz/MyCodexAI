from app.planner.json_parser import JsonParser


text = """
Sure!

{
    "tool":"read_file",
    "arguments":{
        "filename":"hello.txt"
    }
}
"""

print(JsonParser.parse(text))