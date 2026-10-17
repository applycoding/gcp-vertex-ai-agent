"""In-memory catalog and the Firestore adapter against a fake client."""

from app.catalog import seed_products
from app.domain import CaseDraft
from app.firestore_store import FirestoreCatalogStore
from app.store import MemoryStore
from tests.fakes import FakeFirestore, seeded_firestore


def test_memory_and_firestore_search_agree() -> None:
    memory = MemoryStore()
    firestore = FirestoreCatalogStore(seeded_firestore())

    memory_skus = [product.sku for product in memory.search("camp")]
    firestore_skus = [product.sku for product in firestore.search("camp")]

    assert memory_skus == firestore_skus
    assert memory_skus == ["LN-220", "BT-88", "CP-3"]


def test_firestore_reads_sku_from_the_document_id() -> None:
    client = FakeFirestore()
    client.collection("products").document("LN-220").set(
        {
            "name": "Lumen Camp Lantern",
            "description": "Rechargeable lantern.",
            "tags": ["light"],
            "price_cents": 6400,
            "stock": 3,
        }
    )
    store = FirestoreCatalogStore(client)

    product = store.get_product("ln-220")

    assert product is not None
    assert product.sku == "LN-220"
    assert product.stock == 3


def test_firestore_missing_product_and_case_roundtrip() -> None:
    store = FirestoreCatalogStore(seeded_firestore())

    assert store.get_product("NO-1") is None
    created = store.create_case(
        CaseDraft(
            customer_email="ada@example.com",
            subject="Lantern",
            description="The switch sticks.",
            sku="LN-220",
        )
    )
    loaded = store.get_case(created.case_id)

    assert loaded is not None
    assert loaded.status == "open"
    assert loaded.sku == "LN-220"
    assert store.list_cases()[0].case_id == created.case_id


def test_search_ignores_stopwords_and_misses() -> None:
    store = MemoryStore(seed_products())

    assert store.search("the") == []
    assert store.search("zzzz-nope") == []
    assert store.get_product(" tb-100 ") is not None
