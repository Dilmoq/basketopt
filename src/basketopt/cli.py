"""Command-line interface for basketopt."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .db import (
    connect,
    load_prices,
    load_store_rules,
    upsert_item,
    upsert_price,
    upsert_store,
)
from .optimizer import optimize

DEFAULT_DB = "basketopt.db"

SEED_ITEMS = [
    ("молоко простоквашино 3.2% 930мл", "Простоквашино", "молочное", "мл", 930),
    ("яйцо куриное C1 10шт", None, "яйца", "шт", 10),
    ("гречка 1 кг", None, "крупы", "г", 1000),
    ("кофе молотый 250г", None, "кофе", "г", 250),
    ("сахар 1 кг", None, "бакалея", "г", 1000),
    ("масло сливочное 82.5% 180г", None, "молочное", "г", 180),
    ("хлеб белый 400г", None, "хлеб", "г", 400),
    ("макароны 450г", None, "бакалея", "г", 450),
]


def cmd_seed(args: argparse.Namespace) -> int:
    db = Path(args.db)
    conn = connect(db)
    m = upsert_store(conn, "Magnit", free_delivery_from=1500, delivery_fee=199, min_order=0)
    p = upsert_store(conn, "Pyaterochka", free_delivery_from=2500, delivery_fee=99, min_order=1000)
    item_ids = {}
    for name, brand, cat, unit, vol in SEED_ITEMS:
        item_ids[name] = upsert_item(conn, name, brand=brand, category=cat, unit=unit, volume=vol)

    magnit_prices = [94.99, 85.39, 119.0, 349.0, 69.0, 189.0, 49.0, 79.0]
    pyat_prices = [99.0, 80.0, 115.0, 329.0, 72.0, 205.0, 55.0, 85.0]
    for name, price in zip(SEED_ITEMS, magnit_prices, strict=True):
        upsert_price(conn, m, item_ids[name[0]], price)
    for name, price in zip(SEED_ITEMS, pyat_prices, strict=True):
        upsert_price(conn, p, item_ids[name[0]], price)
    conn.commit()
    conn.close()
    print(f"Seeded {len(SEED_ITEMS)} items into {db} (stores: Magnit, Pyaterochka).")
    return 0


def cmd_optimize(args: argparse.Namespace) -> int:
    db = Path(args.db)
    if not db.exists():
        print(f"error: database {db} not found; run `basketopt seed` first", file=sys.stderr)
        return 2
    conn = connect(db)
    rules = load_store_rules(conn)
    prices = load_prices(conn)
    names = {
        row["id"]: row["canonical_name"]
        for row in conn.execute("SELECT id, canonical_name FROM items")
    }
    conn.close()

    wanted = [x.strip() for x in args.basket.split(",") if x.strip()]
    basket_ids = []
    for w in wanted:
        # accept either an id or a (partial) name
        if w.isdigit():
            basket_ids.append(int(w))
            continue
        matches = [iid for iid, n in names.items() if w.lower() in n.lower()]
        if len(matches) != 1:
            print(
                f"error: '{w}' matched {len(matches)} items: {[names[i] for i in matches]}",
                file=sys.stderr,
            )
            return 2
        basket_ids.append(matches[0])

    plan = optimize(basket_ids, prices, rules, max_stores=args.max_stores)
    print("Basket:")
    for iid in basket_ids:
        print(f"  - {names[iid]}")
    print()
    print(f"Total: {plan['total']:.2f} ₽")
    print(f"Baseline (best single store): {plan['baseline_total']:.2f} ₽")
    print(f"Savings: {plan['savings']:.2f} ₽")
    print()
    for store_id in plan["stores"]:
        items = plan["assignment"][store_id]
        print(f"  {rules[store_id]['name']}:")
        for iid in items:
            print(f"    - {names[iid]}  ({prices[store_id][iid]:.2f} ₽)")
        print(f"    subtotal {plan['subtotal'][store_id]:.2f} ₽")
    if plan["missing"]:
        print("Missing:", [names[i] for i in plan["missing"]])
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="basketopt", description="Grocery basket optimizer.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_seed = sub.add_parser("seed", help="create a demo database with sample items and prices")
    p_seed.add_argument("--db", default=DEFAULT_DB)
    p_seed.set_defaults(func=cmd_seed)

    p_opt = sub.add_parser("optimize", help="optimize a basket")
    p_opt.add_argument("--db", default=DEFAULT_DB)
    p_opt.add_argument("--basket", required=True, help="comma-separated item names or ids")
    p_opt.add_argument("--max-stores", type=int, default=2, dest="max_stores")
    p_opt.set_defaults(func=cmd_optimize)

    return parser


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
