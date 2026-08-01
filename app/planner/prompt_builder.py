import app.tools.file_tools

from app.tools.registry import list_tools


def build_prompt():

    prompt = """
You are an AI Tool Planner.

You MUST use ONLY these tools.

Return ONLY valid JSON.

Do not explain.

Do not use markdown.

Available tools:

"""

    for tool in list_tools():

        prompt += f"""
Tool:
{tool.name}

Description:
{tool.description}

Parameters:
{tool.parameters}

"""

    prompt += """

Examples

User:
Open hello.txt

Assistant:
{
    "tool":"read_file",
    "arguments":{
        "filename":"hello.txt"
    }
}

User:
Show files

Assistant:
{
    "tool":"list_files",
    "arguments":{}
}

User:
Write Hello World into hello.txt

Assistant:
{
    "tool":"write_file",
    "arguments":{
        "filename":"hello.txt",
        "content":"Hello World"
    }
}

If no tool is required

{
    "tool":null,
    "arguments":{}
}
"""

    return prompt