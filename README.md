# basketopt — grocery basket optimizer

![CI](https://github.com/Dilmoq/basketopt/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue.svg?logo=python&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-green.svg)

Tell **basketopt** what you need to buy. It finds the cheapest way to get the
whole basket home — including delivery fees, minimum-order thresholds and
promotions — and splits the order across stores when that saves money.

```
You:  молоко, яйца C1, гречка, кофе
Out:  Заказ 1 — Магнит: 4 позиции, 1 347 ₽ (доставка 0 ₽)
      Экономия vs. один магазин: 189 ₽
```

## Status

**Phase 1 (in progress):** Magnit parser works end-to-end on real pages
(price, promotion, old price). Canonical item DB, fuzzy matcher, delivery-aware
optimizer and the web UI are next.

## Why this exists

Price-comparison sites show *single* prices. Real grocery shopping is a
**combinatorial** problem: the cheapest milk is in store A, the cheapest
eggs in store B, but store B has free delivery only above 2 500 ₽ and store
A charges 199 ₽ below 1 500 ₽.  basketopt solves the whole basket, not one
item at a time.

## Data sources

| Store | Method | Status |
|---|---|---|
| Магнит | plain HTTP + Nuxt payload parsing | ✅ working (price, promo, old price) |
| Пятёрочка | JSON API behind an anti-bot challenge | 🔜 Phase 2 (Playwright collector) |
| Лента | closed (401) | not planned |

Magnit pages are fetched politely (retries with backoff, caching in SQLite)
and only from a single region by default.

## Matching

Canonical item DB: each product is stored with normalized attributes
(brand, fat %, volume, category). Raw store names are matched against it with
a tunable fuzzy threshold (≈ 0.75). Anything below the threshold lands in a
review queue and is matched once by hand — after that it works forever.

## Try it (CLI)

```bash
pip install -e ".[dev]"
basketopt seed                          # creates basketopt.db with sample items/prices
basketopt optimize --basket "молоко простоквашино 3.2% 930мл,яйцо куриное C1 10шт,гречка 1 кг"
```

Output shows the best store (or split), per-store subtotals, delivery fees and
savings vs. the best single-store option.


## License

MIT — see [LICENSE](LICENSE).


## Run (web)

```bash
pip install -e ".[dev,web]"
basketopt seed
uvicorn basketopt.web:app --reload
# open http://127.0.0.1:8000
```
