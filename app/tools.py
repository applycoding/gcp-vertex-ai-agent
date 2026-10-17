"""Tool declarations and the dispatcher the agent loop calls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.domain import CaseDraft
from app.parsing import valid_email
from app.store import CatalogStore

_SUBJECT_LIMIT = 200
_DESCRIPTION_LIMIT = 2000


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]


TOOL_SPECS: list[ToolSpec] = [
    ToolSpec(
        name="search_catalog",
        description="Search the Northline Outfitters product catalog by name, SKU, tag, or description.",
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Words from the customer's request, such as 'lantern' or 'TB-100'.",
                }
            },
            "required": ["query"],
        },
    ),
    ToolSpec(
        name="check_stock",
        description="Look up how many units of one SKU are in stock.",
        parameters={
            "type": "object",
            "properties": {
                "sku": {
                    "type": "string",
                    "description": "Catalog SKU, for example LN-220.",
                }
            },
            "required": ["sku"],
        },
    ),
    ToolSpec(
        name="create_support_case",
        description="Open a support case for a customer. Requires an email, subject, and description.",
        parameters={
            "type": "object",
            "properties": {
                "customer_email": {"type": "string", "description": "Customer email address."},
                "subject": {"type": "string", "description": "Short subject line."},
                "description": {"type": "string", "description": "What the customer needs."},
                "sku": {
                    "type": "string",
                    "description": "Optional SKU the case is about.",
                },
            },
            "required": ["customer_email", "subject", "description"],
        },
    ),
]


def execute_tool(store: CatalogStore, name: str, args: dict[str, Any]) -> dict[str, Any]:
    if name == "search_catalog":
        return _search(store, args)
    if name == "check_stock":
        return _stock(store, args)
    if name == "create_support_case":
        return _create_case(store, args)
    return {"error": f"Unknown tool: {name}"}


def _search(store: CatalogStore, args: dict[str, Any]) -> dict[str, Any]:
    query = args.get("query")
    if not isinstance(query, str) or not query.strip():
        return {"error": "query is required"}
    products = store.search(query.strip())
    return {"products": [product.to_dict() for product in products]}


def _stock(store: CatalogStore, args: dict[str, Any]) -> dict[str, Any]:
    sku = args.get("sku")
    if not isinstance(sku, str) or not sku.strip():
        return {"error": "sku is required"}
    product = store.get_product(sku)
    if product is None:
        return {"error": f"Unknown SKU: {sku.strip()}"}
    return {
        "sku": product.sku,
        "name": product.name,
        "quantity": product.stock,
        "in_stock": product.stock > 0,
    }


def _create_case(store: CatalogStore, args: dict[str, Any]) -> dict[str, Any]:
    email = args.get("customer_email")
    subject = args.get("subject")
    description = args.get("description")
    if not isinstance(email, str) or not valid_email(email.strip()):
        return {"error": "customer_email must be an email address"}
    if not isinstance(subject, str) or not subject.strip():
        return {"error": "subject is required"}
    if not isinstance(description, str) or not description.strip():
        return {"error": "description is required"}
    if len(subject.strip()) > _SUBJECT_LIMIT:
        return {"error": "subject is too long"}
    if len(description.strip()) > _DESCRIPTION_LIMIT:
        return {"error": "description is too long"}
    sku = args.get("sku")
    clean_sku: str | None = None
    if sku is not None:
        if not isinstance(sku, str) or not sku.strip():
            return {"error": "sku must be a SKU string when it is provided"}
        product = store.get_product(sku)
        if product is None:
            return {"error": f"Unknown SKU: {sku.strip()}"}
        clean_sku = product.sku
    case = store.create_case(
        CaseDraft(
            customer_email=email.strip(),
            subject=subject.strip(),
            description=description.strip(),
            sku=clean_sku,
        )
    )
    return case.to_dict()
