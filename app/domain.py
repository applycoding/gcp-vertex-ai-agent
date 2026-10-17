"""Catalog and support-case records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4


@dataclass
class Product:
    sku: str
    name: str
    description: str
    tags: list[str]
    price_cents: int
    stock: int

    def to_dict(self) -> dict[str, object]:
        return {
            "sku": self.sku,
            "name": self.name,
            "description": self.description,
            "tags": list(self.tags),
            "price_cents": self.price_cents,
            "stock": self.stock,
        }


@dataclass
class CaseDraft:
    customer_email: str
    subject: str
    description: str
    sku: str | None = None


@dataclass
class SupportCase:
    case_id: str
    customer_email: str
    subject: str
    description: str
    sku: str | None
    status: str
    created_at: str

    def to_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "customer_email": self.customer_email,
            "subject": self.subject,
            "description": self.description,
            "sku": self.sku,
            "status": self.status,
            "created_at": self.created_at,
        }


def new_case(draft: CaseDraft, *, now: datetime | None = None, case_id: str | None = None) -> SupportCase:
    moment = now or datetime.now(timezone.utc)
    created_at = moment.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return SupportCase(
        case_id=case_id or f"SC-{uuid4().hex[:8].upper()}",
        customer_email=draft.customer_email,
        subject=draft.subject,
        description=draft.description,
        sku=draft.sku,
        status="open",
        created_at=created_at,
    )


def product_from_mapping(data: dict[str, object], *, sku: str | None = None) -> Product:
    raw_sku = data.get("sku") or sku
    if not isinstance(raw_sku, str) or not raw_sku.strip():
        raise ValueError("product is missing sku")
    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("product is missing name")
    description = data.get("description") or ""
    tags = data.get("tags") or []
    if not isinstance(description, str) or not isinstance(tags, list):
        raise ValueError("product description or tags has the wrong type")
    return Product(
        sku=raw_sku.strip().upper(),
        name=name.strip(),
        description=description,
        tags=[str(tag) for tag in tags],
        price_cents=int(data.get("price_cents", 0)),
        stock=int(data.get("stock", 0)),
    )


def case_from_mapping(data: dict[str, object]) -> SupportCase:
    sku = data.get("sku")
    return SupportCase(
        case_id=str(data["case_id"]),
        customer_email=str(data["customer_email"]),
        subject=str(data["subject"]),
        description=str(data["description"]),
        sku=str(sku) if isinstance(sku, str) and sku else None,
        status=str(data.get("status") or "open"),
        created_at=str(data["created_at"]),
    )
