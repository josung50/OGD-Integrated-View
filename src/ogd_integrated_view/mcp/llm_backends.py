import json
import uuid
from dataclasses import dataclass
from typing import Any, Protocol

import ollama
import requests


@dataclass
class ToolCallFunction:
    name: str
    arguments: dict[str, Any]


@dataclass
class NormalizedToolCall:
    id: str
    function: ToolCallFunction


@dataclass
class NormalizedMessage:
    content: str | None
    tool_calls: list[NormalizedToolCall]
    history_entry: Any  # 이번 백엔드의 다음 라운드 호출에 그대로 넘길 assistant 메시지 원본


class LLMBackend(Protocol):
    def chat(self, model: str, messages: list[Any], tools: list[dict[str, Any]]) -> NormalizedMessage: ...

    def tool_result_entry(self, tool_call: NormalizedToolCall, tool_name: str, content: str) -> Any: ...


class OllamaBackend:
    """기존 로컬 LLM 경로 — ollama 파이썬 SDK 직접 호출 (동작 변경 없음)."""

    def chat(self, model: str, messages: list[Any], tools: list[dict[str, Any]]) -> NormalizedMessage:
        response = ollama.chat(model=model, messages=messages, tools=tools, think=False)
        message = response.message
        tool_calls = [
            NormalizedToolCall(
                id=getattr(tc, "id", None) or "",
                function=ToolCallFunction(name=tc.function.name, arguments=dict(tc.function.arguments)),
            )
            for tc in (message.tool_calls or [])
        ]
        return NormalizedMessage(
            content=message.content or getattr(message, "thinking", None),
            tool_calls=tool_calls,
            history_entry=message,
        )

    def tool_result_entry(self, tool_call: NormalizedToolCall, tool_name: str, content: str) -> Any:
        return {"role": "tool", "content": content, "tool_name": tool_name}


class VLLMBackend:
    """vLLM(OpenAI 호환 서버) 백엔드. openai SDK 없이 requests로 /chat/completions 직접 호출."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def chat(self, model: str, messages: list[Any], tools: list[dict[str, Any]]) -> NormalizedMessage:
        payload = {
            "model": model,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
            # Qwen3 계열 기본 사고모드(<think>) 끄기 — vLLM/모델 버전에 따라 무시될 수 있음
            "chat_template_kwargs": {"enable_thinking": False},
        }
        url = f"{self.base_url}/chat/completions"
        print(f"[vllm_backend] POST {url} (model={model})", flush=True)
        resp = requests.post(url, json=payload, timeout=120)
        print(f"[vllm_backend] response status={resp.status_code}", flush=True)
        resp.raise_for_status()
        raw_message = resp.json()["choices"][0]["message"]

        tool_calls: list[NormalizedToolCall] = []
        for tc in raw_message.get("tool_calls") or []:
            try:
                arguments = json.loads(tc["function"]["arguments"])
            except (json.JSONDecodeError, TypeError):
                arguments = {}
            tool_calls.append(
                NormalizedToolCall(
                    id=tc.get("id") or f"call_{uuid.uuid4().hex[:8]}",
                    function=ToolCallFunction(name=tc["function"]["name"], arguments=arguments),
                )
            )

        history_entry: dict[str, Any] = {"role": "assistant", "content": raw_message.get("content")}
        if raw_message.get("tool_calls"):
            history_entry["tool_calls"] = raw_message["tool_calls"]

        return NormalizedMessage(content=raw_message.get("content"), tool_calls=tool_calls, history_entry=history_entry)

    def tool_result_entry(self, tool_call: NormalizedToolCall, tool_name: str, content: str) -> Any:
        return {"role": "tool", "tool_call_id": tool_call.id, "content": content}


def build_backend(backend: str, base_url: str | None) -> LLMBackend:
    if backend == "vllm":
        if not base_url:
            raise ValueError("vLLM 백엔드를 사용하려면 base_url이 필요합니다.")
        return VLLMBackend(base_url)
    return OllamaBackend()
