"""Delivery-aware basket optimizer.

Given a basket of item ids, per-store prices and store rules, find the
assignment of items to stores that minimizes the total cost (items + delivery),
optionally splitting across up to ``max_stores`` stores.
"""

from __future__ import annotations

from itertools import combinations


def store_cost(subtotal: float, rule: dict) -> float:
    """Subtotal plus delivery fee (waived above free_delivery_from)."""
    fee = (
        0.0
        if (rule.get("free_delivery_from") is not None and subtotal >= rule["free_delivery_from"])
        else rule.get("delivery_fee", 0.0)
    )
    if subtotal > 0 and subtotal < rule.get("min_order", 0.0):
        fee += 0.0  # min-order shortfalls are reported, not charged here
    return subtotal + fee


def _plan_for_subset(basket, prices, rules, stores_subset):
    """Assign each item to the cheapest store in subset that has it."""
    assignment: dict[int, list[int]] = {s: [] for s in stores_subset}
    subtotal: dict[int, float] = dict.fromkeys(stores_subset, 0.0)
    missing: list[int] = []
    for item in basket:
        best = None
        for s in stores_subset:
            p = prices.get(s, {}).get(item)
            if p is None:
                continue
            if best is None or p < best[1]:
                best = (s, p)
        if best is None:
            missing.append(item)
            continue
        s, p = best
        assignment[s].append(item)
        subtotal[s] += p
    total = 0.0
    for s in stores_subset:
        if assignment[s]:
            total += store_cost(subtotal[s], rules[s])
    return {
        "stores": [s for s in stores_subset if assignment[s]],
        "assignment": {s: items for s, items in assignment.items() if items},
        "subtotal": {s: round(subtotal[s], 2) for s in stores_subset if assignment[s]},
        "total": round(total, 2),
        "missing": missing,
    }


def optimize(basket: list[int], prices: dict, rules: dict, *, max_stores: int = 2) -> dict:
    """Return the best plan (may split across up to ``max_stores`` stores)."""
    if not basket:
        return {
            "stores": [],
            "assignment": {},
            "subtotal": {},
            "total": 0.0,
            "missing": [],
            "baseline": None,
            "savings": 0.0,
        }
    store_ids = list(prices.keys())
    max_stores = min(max_stores, len(store_ids))

    best = None
    for k in range(1, max_stores + 1):
        for subset in combinations(store_ids, k):
            plan = _plan_for_subset(basket, prices, rules, list(subset))
            if plan["missing"]:
                continue
            if best is None or plan["total"] < best["total"]:
                best = plan

    if best is None:
        # fall back: allow missing items, pick fewest missing
        for k in range(1, max_stores + 1):
            for subset in combinations(store_ids, k):
                plan = _plan_for_subset(basket, prices, rules, list(subset))
                if best is None or (len(plan["missing"]), plan["total"]) < (
                    len(best["missing"]),
                    best["total"],
                ):
                    best = plan

    # baseline: best single store covering the whole basket
    baseline = None
    for s in store_ids:
        plan = _plan_for_subset(basket, prices, rules, [s])
        if plan["missing"]:
            continue
        if baseline is None or plan["total"] < baseline["total"]:
            baseline = plan
    if baseline is None:
        baseline = best

    best = dict(best)
    best["baseline_total"] = baseline["total"]
    best["savings"] = round(baseline["total"] - best["total"], 2)
    return best
