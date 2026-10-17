"""Tests for the FastAPI app (no network)."""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from basketopt.db import connect, upsert_item, upsert_price, upsert_store
from basketopt.web import create_app


@pytest.fixture
def seeded_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = connect(path)
    m = upsert_store(conn, "Magnit", free_delivery_from=1500, delivery_fee=199, min_order=0)
    p = upsert_store(conn, "Pyaterochka", free_delivery_from=2500, delivery_fee=99, min_order=1000)
    items = {}
    for name in ["молоко", "яйца", "гречка"]:
        items[name] = upsert_item(conn, name)
    upsert_price(conn, m, items["молоко"], 94.99)
    upsert_price(conn, m, items["яйца"], 85.39)
    upsert_price(conn, m, items["гречка"], 119.0)
    upsert_price(conn, p, items["молоко"], 99.0)
    upsert_price(conn, p, items["яйца"], 80.0)
    upsert_price(conn, p, items["гречка"], 115.0)
    conn.commit()
    conn.close()
    yield path
    os.unlink(path)


class TestWeb:
    def test_health(self, seeded_db):
        client = TestClient(create_app(seeded_db))
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}

    def test_items_listed(self, seeded_db):
        client = TestClient(create_app(seeded_db))
        r = client.get("/items")
        assert r.status_code == 200
        assert len(r.json()) == 3

    def test_index_renders(self, seeded_db):
        client = TestClient(create_app(seeded_db))
        r = client.get("/")
        assert r.status_code == 200
        assert "basketopt" in r.text

    def test_optimize(self, seeded_db):
        client = TestClient(create_app(seeded_db))
        r = client.post("/optimize", json={"basket": [1, 2, 3], "max_stores": 2})
        assert r.status_code == 200
        data = r.json()
        assert data["total"] > 0
        assert data["savings"] >= 0

    def test_optimize_empty_rejected(self, seeded_db):
        client = TestClient(create_app(seeded_db))
        r = client.post("/optimize", json={"basket": [], "max_stores": 2})
        assert r.status_code == 400

    def test_missing_db_returns_503(self, tmp_path):
        client = TestClient(create_app(tmp_path / "nope.db"))
        r = client.get("/items")
        assert r.status_code == 503
