"""Deterministic stand-in used when Vertex AI is not configured.

This is not a language model. It routes obvious catalog, stock, and support
requests through the same tools Gemini would call, so the API can be exercised
with no Google account.
"""

from __future__ import annotations

from typing import Any

from app.conversation import ChatMessage, ModelResponse, ToolCall, ToolResult
from app.parsing import content_tokens, extract_email, extract_sku, strip_email
from app.tools import ToolSpec

HELP_TEXT = (
    "I can search the Northline Outfitters catalog, check stock, and open a support case. "
    "For example: is the Lumen lantern in stock?"
)


class LocalToolRouter:
    def complete(self, messages: list[ChatMessage], tool_specs: list[ToolSpec]) -> ModelResponse:
        del tool_specs
        user_text = _latest_user_text(messages)
        tool_results = _latest_tool_results(messages)
        if tool_results is not None:
            return _after_tools(user_text, tool_results)
        return _from_user(user_text)


def _from_user(text: str) -> ModelResponse:
    sku = extract_sku(text)
    tokens = content_tokens(text)
    if wants_case(text) and extract_email(text) and not tokens and sku is None:
        return ModelResponse(tool_calls=[_case_call(text)])
    if not tokens and sku is None:
        return ModelResponse(text=HELP_TEXT)
    return ModelResponse(tool_calls=[ToolCall(name="search_catalog", args={"query": strip_email(text)})])


def _after_tools(text: str, results: list[ToolResult]) -> ModelResponse:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in results:
        grouped.setdefault(item.name, []).append(item.result)
    if "create_support_case" in grouped:
        return _describe_case(grouped["create_support_case"][-1])
    if "check_stock" in grouped:
        return _after_stock(text, grouped["check_stock"])
    if "search_catalog" in grouped:
        return _after_search(text, grouped["search_catalog"][-1])
    return ModelResponse(text="I could not finish that request from the tool results.")


def _after_search(text: str, result: dict[str, Any]) -> ModelResponse:
    if "error" in result:
        return ModelResponse(text=str(result["error"]))
    products = result.get("products")
    if not isinstance(products, list) or not products:
        if wants_case(text) and extract_email(text):
            return ModelResponse(tool_calls=[_case_call(text)])
        return ModelResponse(text="Nothing in the catalog matched that search.")
    sku = extract_sku(text)
    if sku is not None:
        return ModelResponse(tool_calls=[ToolCall(name="check_stock", args={"sku": sku})])
    if wants_stock(text) and not wants_case(text) and len(products) > 1:
        calls = [
            ToolCall(name="check_stock", args={"sku": str(product["sku"])})
            for product in products[:3]
            if isinstance(product, dict) and product.get("sku")
        ]
        if calls:
            return ModelResponse(tool_calls=calls)
    target = products[0]
    if not isinstance(target, dict):
        return ModelResponse(text="Nothing in the catalog matched that search.")
    if wants_stock(text) or wants_case(text):
        return ModelResponse(tool_calls=[ToolCall(name="check_stock", args={"sku": str(target["sku"])})])
    lines = [_product_line(product) for product in products if isinstance(product, dict)]
    return ModelResponse(text="Catalog matches: " + "; ".join(lines) + ".")


def _after_stock(text: str, stocks: list[dict[str, Any]]) -> ModelResponse:
    if len(stocks) > 1 and not wants_case(text):
        lines = [_stock_sentence(stock) if "error" not in stock else str(stock["error"]) for stock in stocks]
        return ModelResponse(text=" ".join(lines))
    stock = stocks[-1]
    if "error" in stock:
        return ModelResponse(text=str(stock["error"]))
    if wants_case(text):
        email = extract_email(text)
        sentence = _stock_sentence(stock)
        if not email:
            return ModelResponse(text=f"{sentence} Share an email address if you want a support case opened.")
        sku = stock.get("sku")
        name = stock.get("name")
        return ModelResponse(
            tool_calls=[
                _case_call(
                    text,
                    sku=str(sku) if isinstance(sku, str) else None,
                    product_name=str(name) if isinstance(name, str) else None,
                )
            ]
        )
    return ModelResponse(text=_stock_sentence(stock))


def _describe_case(result: dict[str, Any]) -> ModelResponse:
    if "error" in result:
        return ModelResponse(text=str(result["error"]))
    sku = result.get("sku")
    sku_bit = f" for {sku}" if isinstance(sku, str) and sku else ""
    return ModelResponse(
        text=(
            f"Opened support case {result['case_id']}{sku_bit} "
            f"for {result['customer_email']}. Status: {result['status']}."
        )
    )


def _case_call(text: str, *, sku: str | None = None, product_name: str | None = None) -> ToolCall:
    if product_name:
        subject = f"Support request for {product_name}"
    elif sku:
        subject = f"Support request for {sku}"
    else:
        subject = "Support request"
    args: dict[str, Any] = {
        "customer_email": extract_email(text) or "",
        "subject": subject,
        "description": text.strip()[:2000],
    }
    if sku:
        args["sku"] = sku
    return ToolCall(name="create_support_case", args=args)


def wants_stock(text: str) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in ("stock", "available", "availability", "how many"))


def wants_case(text: str) -> bool:
    lowered = text.lower()
    return any(
        phrase in lowered
        for phrase in ("support case", "open a case", "create a case", "file a case", "restock")
    )


def _stock_sentence(stock: dict[str, Any]) -> str:
    name = stock.get("name", stock.get("sku", "That item"))
    sku = stock.get("sku", "")
    quantity = stock.get("quantity", 0)
    label = f"{name} ({sku})" if sku else str(name)
    if quantity == 0:
        return f"{label} is out of stock."
    unit = "unit" if quantity == 1 else "units"
    return f"{label} has {quantity} {unit} in stock."


def _product_line(product: dict[str, Any]) -> str:
    cents = int(product.get("price_cents", 0))
    price = f"${cents // 100}.{cents % 100:02d}"
    return f"{product.get('name')} ({product.get('sku')}) {price}"


def _latest_user_text(messages: list[ChatMessage]) -> str:
    for message in reversed(messages):
        if message.role == "user" and message.text:
            return message.text
    return ""


def _latest_tool_results(messages: list[ChatMessage]) -> list[ToolResult] | None:
    if not messages or messages[-1].role != "tool":
        return None
    return messages[-1].tool_results
