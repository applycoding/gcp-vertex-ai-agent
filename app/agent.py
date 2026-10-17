"""Tool-calling loop. The model client is injected; tests pass a script."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from app.conversation import ChatMessage, ModelResponse, ToolCall, ToolResult
from app.errors import ModelError
from app.logging_setup import get_logger, log_event
from app.store import CatalogStore
from app.tools import TOOL_SPECS, ToolSpec, execute_tool

logger = get_logger()

LIMIT_REPLY = "I hit the tool-call limit before I could finish. Try a narrower question."


class ModelClient(Protocol):
    def complete(self, messages: list[ChatMessage], tool_specs: list[ToolSpec]) -> ModelResponse:
        """Return the next model turn for this transcript."""


@dataclass
class ExecutedTool:
    name: str
    args: dict[str, Any]
    result: dict[str, Any]


@dataclass
class AgentResult:
    reply: str
    trace: list[ExecutedTool] = field(default_factory=list)
    messages: list[ChatMessage] = field(default_factory=list)


class Agent:
    def __init__(self, model: ModelClient, store: CatalogStore, *, max_tool_rounds: int = 4) -> None:
        if max_tool_rounds < 1:
            raise ValueError("max_tool_rounds must be at least 1")
        self._model = model
        self._store = store
        self._max_tool_rounds = max_tool_rounds

    def run(self, message: str, history: list[ChatMessage] | None = None) -> AgentResult:
        messages = list(history or [])
        messages.append(ChatMessage(role="user", text=message))
        trace: list[ExecutedTool] = []
        for _ in range(self._max_tool_rounds):
            response = self._model.complete(messages, TOOL_SPECS)
            if not response.tool_calls:
                reply = response.text or ""
                messages.append(ChatMessage(role="model", text=reply))
                return AgentResult(reply=reply, trace=trace, messages=messages)
            self._execute(response, messages, trace)
        return AgentResult(reply=LIMIT_REPLY, trace=trace, messages=messages)

    def _execute(
        self,
        response: ModelResponse,
        messages: list[ChatMessage],
        trace: list[ExecutedTool],
    ) -> None:
        stored_calls = [ToolCall(name=call.name, args=dict(call.args)) for call in response.tool_calls]
        messages.append(ChatMessage(role="model", text=response.text, tool_calls=stored_calls))
        results: list[ToolResult] = []
        for call in stored_calls:
            try:
                result = execute_tool(self._store, call.name, call.args)
            except Exception:
                logger.exception("tool raised", extra={"extra_fields": {"tool": call.name}})
                result = {"error": f"{call.name} failed"}
            results.append(ToolResult(name=call.name, result=result))
            trace.append(ExecutedTool(name=call.name, args=dict(call.args), result=result))
            log_event(
                logger,
                "tool finished",
                tool=call.name,
                ok="error" not in result,
            )
        messages.append(ChatMessage(role="tool", tool_results=results))
