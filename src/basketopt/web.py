"""FastAPI application for basketopt."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from .db import connect, load_prices, load_store_rules
from .optimizer import optimize


class OptimizeRequest(BaseModel):
    basket: list[int]
    max_stores: int = 2


INDEX_HTML = """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>basketopt — оптимизатор корзины</title>
<style>
body{font-family:system-ui,sans-serif;max-width:720px;margin:2rem auto;padding:0 1rem}
h1{margin-bottom:.25rem}
.card{border:1px solid #ddd;border-radius:8px;padding:1rem;margin:1rem 0}
button{padding:.5rem 1rem;cursor:pointer}
pre{background:#f5f5f5;padding:1rem;border-radius:6px;overflow:auto}
</style>
</head>
<body>
<h1>basketopt</h1>
<p>Введите id товаров через запятую — получите оптимальный план покупки.</p>
<div class="card">
  <label>Корзина (id товаров): <input id="basket" size="40" value="1,2,3"></label>
  <label>Макс. магазинов: <input id="maxstores" size="3" value="2"></label>
  <button onclick="run()">Оптимизировать</button>
</div>
<pre id="out"></pre>
<script>
async function run(){
  const basket = document.getElementById('basket').value.split(',').map(
    x => parseInt(x.trim())
  ).filter(x => !isNaN(x));
  const ms = parseInt(document.getElementById('maxstores').value) || 2;
  const r = await fetch('/optimize', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({basket, max_stores: ms})
  });
  const data = await r.json();
  document.getElementById('out').textContent = JSON.stringify(data,null,2);
}
</script>
</body>
</html>
"""


def create_app(db_path: str | Path | None = None) -> FastAPI:
    if db_path is None:
        db_path = os.getenv("BASKETOPT_DB", "basketopt.db")
    app = FastAPI(title="basketopt", version="0.1.0")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return INDEX_HTML

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    def _conn():
        path = Path(db_path)
        if not path.exists():
            raise HTTPException(status_code=503, detail=f"database not found: {path}")
        return connect(path)

    @app.get("/items")
    def items() -> list[dict]:
        conn = _conn()
        try:
            rows = conn.execute(
                "SELECT id, canonical_name, brand, category, unit, volume FROM items ORDER BY id"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    @app.get("/stores")
    def stores() -> list[dict]:
        conn = _conn()
        try:
            return list(load_store_rules(conn).values())
        finally:
            conn.close()

    @app.post("/optimize")
    def optimize_endpoint(req: OptimizeRequest) -> dict:
        conn = _conn()
        try:
            rules = load_store_rules(conn)
            prices = load_prices(conn)
        finally:
            conn.close()
        if not req.basket:
            raise HTTPException(status_code=400, detail="basket is empty")
        plan = optimize(req.basket, prices, rules, max_stores=req.max_stores)
        return plan

    return app


app = create_app()
