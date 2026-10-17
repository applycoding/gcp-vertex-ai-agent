"""Tool argument checks and the local router that stands in for Gemini."""

from app.agent import Agent
from app.conversation import ToolCall
from app.local_router import LocalToolRouter
from app.store import MemoryStore
from app.tools import execute_tool


def test_stock_requires_a_sku() -> None:
    result = execute_tool(MemoryStore(), "check_stock", {})
    assert result == {"error": "sku is required"}


def test_unknown_sku() -> None:
    result = execute_tool(MemoryStore(), "check_stock", {"sku": "NO-1"})
    assert result == {"error": "Unknown SKU: NO-1"}


def test_case_rejects_a_bad_email_and_an_unknown_sku() -> None:
    store = MemoryStore()
    bad_email = execute_tool(
        store,
        "create_support_case",
        {
            "customer_email": "not-an-email",
            "subject": "Help",
            "description": "The zipper failed.",
        },
    )
    unknown_sku = execute_tool(
        store,
        "create_support_case",
        {
            "customer_email": "ada@example.com",
            "subject": "Missing",
            "description": "No such sku",
            "sku": "NO-1",
        },
    )

    assert bad_email["error"] == "customer_email must be an email address"
    assert unknown_sku["error"] == "Unknown SKU: NO-1"
    assert store.list_cases() == []


def test_case_is_stored() -> None:
    store = MemoryStore()
    result = execute_tool(
        store,
        "create_support_case",
        {
            "customer_email": "ada@example.com",
            "subject": "Zipper",
            "description": "The daypack zipper split.",
            "sku": "pk-14",
        },
    )

    stored = store.get_case(result["case_id"])
    assert stored is not None
    assert stored.sku == "PK-14"
    assert stored.status == "open"


def test_local_router_checks_lantern_stock() -> None:
    result = Agent(LocalToolRouter(), MemoryStore()).run("Is the Lumen lantern in stock?")

    assert [item.name for item in result.trace] == ["search_catalog", "check_stock"]
    assert result.trace[0].args["query"] == "lumen lantern"
    assert result.trace[1].result["sku"] == "LN-220"
    assert result.trace[1].result["quantity"] == 24
    assert "24" in result.reply
    assert "in stock" in result.reply


def test_local_router_opens_a_case_for_the_out_of_stock_jacket() -> None:
    store = MemoryStore()
    result = Agent(LocalToolRouter(), store).run(
        "Please open a case for ada@example.com about the Trailblazer jacket."
    )

    assert [item.name for item in result.trace] == [
        "search_catalog",
        "check_stock",
        "create_support_case",
    ]
    assert result.trace[0].args["query"] == "trailblazer jacket"
    case = store.get_case(result.trace[-1].result["case_id"])
    assert case is not None
    assert case.sku == "TB-100"
    assert case.customer_email == "ada@example.com"
    assert case.case_id in result.reply


def test_local_router_lists_a_product_without_calling_stock() -> None:
    result = Agent(LocalToolRouter(), MemoryStore()).run("Show me the copper camp mug")

    assert [item.name for item in result.trace] == ["search_catalog"]
    assert "Copper Camp Mug" in result.reply
    assert "$28.00" in result.reply


def test_local_router_help_for_a_greeting() -> None:
    result = Agent(LocalToolRouter(), MemoryStore()).run("hello")

    assert result.trace == []
    assert "Lumen lantern" in result.reply


def test_execute_tool_accepts_the_call_shape_used_by_the_loop() -> None:
    call = ToolCall("search_catalog", {"query": "TRAILBLAZER"})
    result = execute_tool(MemoryStore(), call.name, call.args)
    assert result["products"][0]["sku"] == "TB-100"
