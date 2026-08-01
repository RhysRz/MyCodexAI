from app.agents.ollama_agent import OllamaAgent
from app.planner.prompt_builder import build_prompt
from app.planner.json_parser import JsonParser


class ToolPlanner:

    @staticmethod
    def plan(message: str):

        system_prompt = build_prompt()

        response = OllamaAgent.ask([
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": message
            }
        ])

        return JsonParser.parse(response)
