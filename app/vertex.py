"""Gemini on Vertex AI via the google-genai SDK.

Automatic function calling is disabled. This process executes tools itself so
the same loop can run against a scripted client in tests.
"""

from __future__ import annotations

from typing import Any, Protocol

from google import genai
from google.genai import types

from app.config import Settings
from app.conversation import ChatMessage, ModelResponse, ToolCall
from app.errors import ModelError
from app.tools import ToolSpec


class _GenerateModels(Protocol):
    def generate_content(
        self,
        *,
        model: str,
        contents: list[types.Content],
        config: types.GenerateContentConfig,
    ) -> Any:
        """One Gemini generateContent call."""


class _GenAIClient(Protocol):
    models: _GenerateModels


class VertexGeminiClient:
    def __init__(self, genai_client: _GenAIClient, *, model: str, system_prompt: str) -> None:
        self._client = genai_client
        self._model = model
        self._system_prompt = system_prompt

    def complete(self, messages: list[ChatMessage], tool_specs: list[ToolSpec]) -> ModelResponse:
        if not messages:
            raise ModelError("no messages to send")
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=[_content(message) for message in messages],
                config=_config(tool_specs, self._system_prompt),
            )
        except ModelError:
            raise
        except Exception as exc:
            raise ModelError("vertex generate_content failed") from exc
        try:
            return parse_model_response(response)
        except ModelError:
            raise
        except Exception as exc:
            raise ModelError("could not read the model response") from exc


def build_vertex_client(settings: Settings, system_prompt: str) -> VertexGeminiClient:
    if not settings.project_id:
        raise ModelError("GOOGLE_CLOUD_PROJECT is required when MODEL_BACKEND=vertex")
    client = genai.Client(
        vertexai=True,
        project=settings.project_id,
        location=settings.location,
    )
    return VertexGeminiClient(client, model=settings.model_name, system_prompt=system_prompt)


def parse_model_response(response: Any) -> ModelResponse:
    calls: list[ToolCall] = []
    raw_calls = getattr(response, "function_calls", None) or []
    for function_call in raw_calls:
        parsed = _tool_call(function_call)
        if parsed is not None:
            calls.append(parsed)
    texts: list[str] = []
    candidates = getattr(response, "candidates", None) or []
    if candidates:
        content = getattr(candidates[0], "content", None)
        parts = getattr(content, "parts", None) or []
        for part in parts:
            text = getattr(part, "text", None)
            if isinstance(text, str) and text:
                texts.append(text)
            if raw_calls:
                continue
            parsed = _tool_call(getattr(part, "function_call", None))
            if parsed is not None:
                calls.append(parsed)
    if not texts and not calls:
        raise ModelError("model returned no text or tool calls")
    return ModelResponse(text="\n".join(texts) if texts else None, tool_calls=calls)


def _config(tool_specs: list[ToolSpec], system_prompt: str) -> types.GenerateContentConfig:
    declarations = [
        types.FunctionDeclaration(
            name=spec.name,
            description=spec.description,
            parameters_json_schema=spec.parameters,
        )
        for spec in tool_specs
    ]
    return types.GenerateContentConfig(
        tools=[types.Tool(function_declarations=declarations)],
        temperature=0,
        system_instruction=system_prompt,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )


def _content(message: ChatMessage) -> types.Content:
    if message.role == "user":
        return types.Content(role="user", parts=[types.Part.from_text(text=message.text or "")])
    if message.role == "model":
        parts: list[types.Part] = []
        if message.text:
            parts.append(types.Part.from_text(text=message.text))
        for call in message.tool_calls:
            parts.append(types.Part.from_function_call(name=call.name, args=dict(call.args)))
        if not parts:
            parts.append(types.Part.from_text(text=""))
        return types.Content(role="model", parts=parts)
    if message.role == "tool":
        parts = [
            types.Part.from_function_response(name=result.name, response=dict(result.result))
            for result in message.tool_results
        ]
        if not parts:
            parts.append(types.Part.from_text(text=""))
        return types.Content(role="tool", parts=parts)
    raise ModelError(f"unknown message role: {message.role}")


def _tool_call(function_call: Any) -> ToolCall | None:
    if function_call is None:
        return None
    name = getattr(function_call, "name", None)
    if not isinstance(name, str) or not name:
        return None
    args = getattr(function_call, "args", None) or {}
    return ToolCall(name=name, args=dict(args))
