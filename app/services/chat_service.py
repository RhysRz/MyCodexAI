"""Safe, per-user conversational chat backed by the local Ollama model."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterator
from threading import RLock

from app.agents.ollama_agent import OllamaAgent
from app.core.settings import settings
from app.memory.session import SessionMemory


class ChatService:
    """Normal chat never reads files, plans tools, or performs side effects."""

    _history_limit = 16
    _lock = RLock()
    _histories: dict[str, deque[dict[str, str]]] = {}
    # Kept only for old local callers without an authenticated user. The web
    # route always supplies an owner id, so users never share this memory.
    memory = SessionMemory()

    _system_prompt = """/no_think
You are MyCodex in normal chat mode. MyCodex is a male AI persona.

Identity and voice:
- Your name is MyCodex. If the user asks your name, say that your name is MyCodex.
- You identify as male. If the user asks your gender, say that you are male.
- When replying in Thai, use a warm, professional masculine voice and natural
  masculine polite particles such as "ครับ" when appropriate. Do not
  overuse them, and do not bring up your gender unless the user asks.

Language policy:
- Thai is the default. When the user writes Thai, reply entirely in natural,
  clear Thai, as a helpful ChatGPT-style assistant would.
- Understand everyday Thai, informal wording, common abbreviations, and small
  typing mistakes. Infer the most likely meaning; ask one short clarification
  only when the ambiguity would materially change the answer.
- Use the language requested by the user when they explicitly ask for another
  language. Keep programming code, identifiers, commands, and quoted technical
  terms in their appropriate original form.

Answer directly and helpfully. Be concise unless the user asks for detail. This
mode is for conversation, explanation, reasoning, translation, planning, and
drafting text or code in the reply. It cannot inspect local files, run commands,
browse the web, create files, or change a project.

Accuracy rules:
- Answer the user's actual question first. Do not fill a simple question with a
  generic list of unrelated capabilities.
- Never claim that a website, PDF, file, project, test, or command was created,
  checked, or run in normal chat. You may offer a plan or a draft in the reply.
- When asked what you can do, clearly distinguish: Chat can discuss and draft;
  Agent mode can inspect or make project changes, subject to the user's approval.
- State uncertainty plainly rather than guessing. Ask one short clarification
  only if it materially changes the answer.
- Think through the answer privately, then present the conclusion and the most
  useful next steps in clear Thai."""

    @classmethod
    def chat(cls, message: str, owner_id: str | None = None) -> str:
        message = message.strip()
        if not message:
            raise ValueError("message must not be empty")

        if owner_id is None:
            return cls._anonymous_chat(message)

        with cls._lock:
            history = list(cls._history_for(owner_id))

        answer = OllamaAgent.ask(
            [
                {"role": "system", "content": cls._system_prompt},
                *history,
                {"role": "user", "content": message},
            ],
            model=settings.ollama_chat_model or settings.ollama_model,
            temperature=settings.ollama_chat_temperature,
            think=settings.ollama_chat_thinking,
        ).strip()
        if not answer:
            answer = "I could not produce a response. Please try again."

        with cls._lock:
            conversation = cls._history_for(owner_id)
            conversation.append({"role": "user", "content": message})
            conversation.append({"role": "assistant", "content": answer})
        return answer

    @classmethod
    def stream(cls, message: str, owner_id: str) -> Iterator[str]:
        """Stream a normal-chat answer and persist it only after completion."""
        message = message.strip()
        if not message:
            raise ValueError("message must not be empty")

        with cls._lock:
            history = list(cls._history_for(owner_id))

        answer_parts: list[str] = []
        completed = False
        try:
            for chunk in OllamaAgent.stream(
                [
                    {"role": "system", "content": cls._system_prompt},
                    *history,
                    {"role": "user", "content": message},
                ],
                model=settings.ollama_chat_model or settings.ollama_model,
                temperature=settings.ollama_chat_temperature,
            ):
                if not chunk:
                    continue
                answer_parts.append(chunk)
                yield chunk
            if not answer_parts:
                fallback = "ขออภัยครับ ผมยังสร้างคำตอบไม่ได้ ลองใหม่อีกครั้งได้เลย"
                answer_parts.append(fallback)
                yield fallback
            completed = True
        finally:
            if completed:
                answer = "".join(answer_parts).strip()
                with cls._lock:
                    conversation = cls._history_for(owner_id)
                    conversation.append({"role": "user", "content": message})
                    conversation.append({"role": "assistant", "content": answer})

    @classmethod
    def history(cls, owner_id: str) -> list[dict[str, str]]:
        with cls._lock:
            return [dict(message) for message in cls._history_for(owner_id)]

    @classmethod
    def _history_for(cls, owner_id: str) -> deque[dict[str, str]]:
        if owner_id not in cls._histories:
            cls._histories[owner_id] = deque(maxlen=cls._history_limit)
        return cls._histories[owner_id]

    @classmethod
    def _anonymous_chat(cls, message: str) -> str:
        """Compatibility path for old local callers; not used by authenticated UI."""
        cls.memory.add_user(message)
        answer = OllamaAgent.ask(
            [
                {"role": "system", "content": cls._system_prompt},
                *cls.memory.get()[-cls._history_limit :],
            ],
            model=settings.ollama_chat_model or settings.ollama_model,
            temperature=settings.ollama_chat_temperature,
            think=settings.ollama_chat_thinking,
        ).strip()
        if not answer:
            answer = "I could not produce a response. Please try again."
        cls.memory.add_assistant(answer)
        return answer
