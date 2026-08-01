from contextlib import contextmanager
from contextvars import ContextVar
from threading import BoundedSemaphore
from collections.abc import Callable, Iterator
from typing import Any, List
from urllib.parse import urlsplit
import json
import re

from openai import OpenAI
import requests

from app.core.settings import settings
from app.services.resource_service import ResourceService


class OllamaAgent:

    client = OpenAI(
        base_url=settings.ollama_url,
        api_key=settings.ollama_api_key,
        timeout=settings.ollama_timeout_seconds
    )
    # The agent runner is already sequential, but regular chat calls can arrive
    # at the same time. One shared inference slot prevents CPU/RAM contention.
    _inference_slots = BoundedSemaphore(max(1, settings.ollama_max_concurrent_requests))
    _resource_observer: ContextVar[Callable[[dict[str, Any] | None], None] | None] = ContextVar(
        "mycodexai_resource_observer",
        default=None,
    )

    @classmethod
    @contextmanager
    def observe_resources(cls, observer: Callable[[dict[str, Any] | None], None]) -> Iterator[None]:
        """Attach a run-local progress observer without changing model calls."""
        token = cls._resource_observer.set(observer)
        try:
            yield
        finally:
            cls._resource_observer.reset(token)

    @classmethod
    def _resource_options(cls) -> dict[str, Any]:
        return {
            "options": {"num_thread": settings.ollama_inference_threads},
            "keep_alive": f"{settings.ollama_keep_alive_seconds}s",
        }

    @classmethod
    def ask(
        cls,
        messages: List[dict],
        *,
        model: str | None = None,
        temperature: float | None = None,
        think: bool | None = None,
    ) -> str:
        ResourceService.wait_for_capacity(cls._resource_observer.get())
        with cls._inference_slots:
            if think is not None:
                return cls._ask_native_chat(messages, model=model, temperature=temperature, think=think)
            response = cls.client.chat.completions.create(
                model=model or settings.ollama_model,
                messages=messages,
                max_tokens=settings.ollama_max_tokens,
                **({"temperature": temperature} if temperature is not None else {}),
                extra_body=cls._resource_options(),
            )

        return response.choices[0].message.content or ""

    @classmethod
    def stream(
        cls,
        messages: List[dict],
        *,
        model: str | None = None,
        temperature: float | None = None,
    ) -> Iterator[str]:
        """Yield visible chat text from Ollama as it is generated.

        This intentionally uses Ollama's native streaming endpoint so the UI
        can begin rendering and speaking a reply before the full answer exists.
        The shared inference slot is held for the generator's lifetime.
        """
        ResourceService.wait_for_capacity(cls._resource_observer.get())
        cls._inference_slots.acquire()
        response = None
        try:
            endpoint = urlsplit(settings.ollama_url)
            base_url = f"{endpoint.scheme}://{endpoint.netloc}"
            options: dict[str, Any] = {"num_thread": settings.ollama_inference_threads}
            if temperature is not None:
                options["temperature"] = temperature
            response = requests.post(
                f"{base_url}/api/chat",
                json={
                    "model": model or settings.ollama_model,
                    "messages": messages,
                    "stream": True,
                    # Voice chat should never expose model reasoning while it
                    # is being streamed to the browser.
                    "think": False,
                    "keep_alive": f"{settings.ollama_keep_alive_seconds}s",
                    "options": options,
                },
                stream=True,
                timeout=settings.ollama_timeout_seconds,
            )
            response.raise_for_status()
            visibility: dict[str, Any] = {"buffer": "", "thinking": False}
            for raw_line in response.iter_lines(decode_unicode=True):
                if not raw_line:
                    continue
                payload = json.loads(raw_line)
                message = payload.get("message") or {}
                content = str(message.get("content") or "")
                visible = cls._visible_stream_piece(content, visibility)
                if visible:
                    yield visible
                if payload.get("done"):
                    break
            final_piece = cls._visible_stream_piece("", visibility, final=True)
            if final_piece:
                yield final_piece
        finally:
            if response is not None:
                response.close()
            cls._inference_slots.release()

    @staticmethod
    def _visible_stream_piece(content: str, state: dict[str, Any], *, final: bool = False) -> str:
        """Strip a possibly chunked <think> block without leaking it mid-stream."""
        buffer = f"{state.get('buffer', '')}{content}"
        output: list[str] = []
        marker = "<think>"
        end_marker = "</think>"
        while buffer:
            lowered = buffer.lower()
            if state.get("thinking"):
                end = lowered.find(end_marker)
                if end < 0:
                    buffer = ""
                    break
                buffer = buffer[end + len(end_marker):]
                state["thinking"] = False
                continue
            start = lowered.find(marker)
            if start >= 0:
                output.append(buffer[:start])
                buffer = buffer[start + len(marker):]
                state["thinking"] = True
                continue
            # Hold only the possible beginning of a marker between chunks.
            if final:
                output.append(buffer)
                buffer = ""
            elif len(buffer) > len(marker) - 1:
                output.append(buffer[: -(len(marker) - 1)])
                buffer = buffer[-(len(marker) - 1):]
            break
        state["buffer"] = buffer
        return "".join(output)

    @classmethod
    def _ask_native_chat(
        cls,
        messages: List[dict],
        *,
        model: str | None,
        temperature: float | None,
        think: bool,
    ) -> str:
        """Use Ollama's native chat API when an explicit thinking mode is needed."""
        endpoint = urlsplit(settings.ollama_url)
        base_url = f"{endpoint.scheme}://{endpoint.netloc}"
        options: dict[str, Any] = {"num_thread": settings.ollama_inference_threads}
        if temperature is not None:
            options["temperature"] = temperature
        response = requests.post(
            f"{base_url}/api/chat",
            json={
                "model": model or settings.ollama_model,
                "messages": messages,
                "stream": False,
                "think": think,
                "keep_alive": f"{settings.ollama_keep_alive_seconds}s",
                "options": options,
            },
            timeout=settings.ollama_timeout_seconds,
        )
        response.raise_for_status()
        message = response.json().get("message") or {}
        return cls._visible_answer(str(message.get("content") or ""))

    @staticmethod
    def _visible_answer(content: str) -> str:
        """Remove reasoning traces emitted by older Qwen/Ollama combinations."""
        answer = re.sub(r"<think>.*?</think>\s*", "", content, flags=re.IGNORECASE | re.DOTALL)
        if answer.lstrip().lower().startswith("<think>"):
            return ""
        return answer.strip()


    @classmethod
    def ask_json(cls, messages: List[dict]) -> str:
        ResourceService.wait_for_capacity(cls._resource_observer.get())
        with cls._inference_slots:
            response = cls.client.chat.completions.create(
                model=settings.ollama_model,
                messages=messages,
                max_tokens=settings.ollama_max_tokens,
                temperature=0,
                response_format={"type": "json_object"},
                extra_body=cls._resource_options(),
            )

        return response.choices[0].message.content or ""
