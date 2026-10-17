"""Agent loop with a scripted model and the in-memory catalog."""

from app.agent import LIMIT_REPLY, Agent
from app.conversation import ModelResponse, ToolCall
from app.store import MemoryStore
from tests.fakes import ScriptedModel


def test_scripted_tool_results_are_fed_back() -> None:
    store = MemoryStore()
    model = ScriptedModel(
        [
            ModelResponse(tool_calls=[ToolCall("search_catalog", {"query": "lantern"})]),
            ModelResponse(tool_calls=[ToolCall("check_stock", {"sku": "LN-220"})]),
            ModelResponse(text="Lantern stock is 24."),
        ]
    )
    result = Agent(model, store).run("Do you have a lantern?")

    assert result.reply == "Lantern stock is 24."
    assert [item.name for item in result.trace] == ["search_catalog", "check_stock"]
    assert result.trace[0].result["products"][0]["sku"] == "LN-220"
    assert result.trace[1].result["quantity"] == 24
    feedback = model.seen[1][-1]
    assert feedback.role == "tool"
    assert feedback.tool_results[0].result["products"][0]["sku"] == "LN-220"
    stock_feedback = model.seen[2][-1]
    assert stock_feedback.tool_results[0].result["quantity"] == 24


def test_unknown_tool_is_returned_to_the_model() -> None:
    model = ScriptedModel(
        [
            ModelResponse(tool_calls=[ToolCall("refund_order", {"order_id": "1"})]),
            ModelResponse(text="I cannot refund orders from here."),
        ]
    )
    result = Agent(model, MemoryStore()).run("Refund order 1")

    assert result.reply == "I cannot refund orders from here."
    assert result.trace[0].result == {"error": "Unknown tool: refund_order"}
    assert model.seen[1][-1].tool_results[0].result["error"] == "Unknown tool: refund_order"


def test_direct_answer_skips_tools() -> None:
    model = ScriptedModel([ModelResponse(text="Hello from the script.")])
    result = Agent(model, MemoryStore()).run("hi")

    assert result.reply == "Hello from the script."
    assert result.trace == []


def test_tool_round_limit() -> None:
    model = ScriptedModel(
        [
            ModelResponse(tool_calls=[ToolCall("check_stock", {"sku": "LN-220"})]),
            ModelResponse(tool_calls=[ToolCall("check_stock", {"sku": "LN-220"})]),
        ]
    )
    result = Agent(model, MemoryStore(), max_tool_rounds=2).run("keep checking")

    assert result.reply == LIMIT_REPLY
    assert len(result.trace) == 2
    assert model.script == []


def test_out_of_stock_case_from_scripted_calls() -> None:
    store = MemoryStore()
    model = ScriptedModel(
        [
            ModelResponse(tool_calls=[ToolCall("search_catalog", {"query": "trailblazer"})]),
            ModelResponse(tool_calls=[ToolCall("check_stock", {"sku": "TB-100"})]),
            ModelResponse(
                tool_calls=[
                    ToolCall(
                        "create_support_case",
                        {
                            "customer_email": "ada@example.com",
                            "subject": "Trailblazer restock",
                            "description": "Please write when the jacket is back.",
                            "sku": "TB-100",
                        },
                    )
                ]
            ),
            ModelResponse(text="I opened a support case for the jacket."),
        ]
    )
    result = Agent(model, store).run("The Trailblazer is out of stock. Open a case for ada@example.com.")

    assert result.reply == "I opened a support case for the jacket."
    assert [item.name for item in result.trace] == [
        "search_catalog",
        "check_stock",
        "create_support_case",
    ]
    case_id = result.trace[-1].result["case_id"]
    stored = store.get_case(case_id)
    assert stored is not None
    assert stored.status == "open"
    assert stored.sku == "TB-100"
    assert stored.customer_email == "ada@example.com"
