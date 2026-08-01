"""Strict protocol handling for Ollama-driven agent decisions."""

import json
from typing import Any


class AgentProtocol:
    @staticmethod
    def parse(raw_response: str) -> dict[str, Any] | None:
        raw_response = raw_response.strip()

        candidates = []
        try:
            candidates.append(json.loads(raw_response))
        except json.JSONDecodeError:
            pass

        decoder = json.JSONDecoder()
        for index, character in enumerate(raw_response):
            if character != "{":
                continue

            try:
                data, _ = decoder.raw_decode(raw_response[index:])
            except json.JSONDecodeError:
                continue

            candidates.append(data)

        for data in candidates:

            action = data.get("action")
            if action is None and "tool" in data:
                action = {
                    "tool": data.get("tool"),
                    "arguments": data.get("arguments", {}),
                }

            if not isinstance(action, dict):
                continue

            tool = action.get("tool")
            arguments = action.get("arguments", {})
            if not isinstance(tool, str) or not isinstance(arguments, dict):
                continue

            return {
                "tool": tool,
                "arguments": arguments,
                "summary": data.get("summary", ""),
            }

        return None
