"""Tests for matcher and optimizer (pure logic, no network)."""

from basketopt.matcher import best_match, normalize, score, tokens
from basketopt.optimizer import optimize, store_cost


class TestNormalize:
    def test_lowercases_and_unifies_units(self):
        assert normalize("Молоко Простоквашино 3.2% 930мл") == "молоко простоквашино 3.2% 930мл"

    def test_tokens_drop_stopwords(self):
        assert "г" not in tokens("Гречка 1 кг")
        assert "гречка" in tokens("Гречка 1 кг")


class TestScore:
    def test_identical_high(self):
        assert score("молоко простоквашино 3.2% 930мл", "молоко простоквашино 3.2% 930мл") > 0.9

    def test_different_low(self):
        assert score("молоко простоквашино 3.2% 930мл", "яйцо куриное C1 10шт") < 0.4


class TestBestMatch:
    def test_returns_match_above_threshold(self):
        cands = [(1, "молоко простоквашино 3.2% 930мл"), (2, "яйцо куриное C1 10шт")]
        res = best_match("Молоко Простоквашино паст. 2.5% 930 мл", cands, threshold=0.5)
        assert res is not None
        assert res[0] == 1

    def test_returns_none_below_threshold(self):
        cands = [(1, "молоко простоквашино 3.2% 930мл")]
        assert best_match("бананы чикита 1кг", cands, threshold=0.9) is None


class TestStoreCost:
    def test_free_delivery_waived(self):
        assert (
            store_cost(2000, {"free_delivery_from": 1500, "delivery_fee": 199, "min_order": 0})
            == 2000
        )

    def test_delivery_fee_added(self):
        assert (
            store_cost(1000, {"free_delivery_from": 1500, "delivery_fee": 199, "min_order": 0})
            == 1199
        )


class TestOptimizer:
    RULES = {
        1: {"name": "Magnit", "free_delivery_from": 1500, "delivery_fee": 199, "min_order": 0},
        2: {
            "name": "Pyaterochka",
            "free_delivery_from": 2500,
            "delivery_fee": 99,
            "min_order": 1000,
        },
    }
    PRICES = {
        1: {1: 94.99, 2: 85.39, 3: 120.0},
        2: {1: 99.0, 2: 80.0, 3: 115.0},
    }

    def test_single_store_when_cheaper_overall(self):
        plan = optimize([1, 2, 3], self.PRICES, self.RULES, max_stores=1)
        # Magnit subtotal 300.38 + delivery 199 = 499.38 ; Pyaterochka 294 + 99 = 393
        assert plan["total"] == 393.0
        assert plan["stores"] == [2]

    def test_split_can_beat_single_store(self):
        # item 3 only in store1 cheap, item2 only in store2 cheap -> split
        prices = {1: {1: 94.99, 3: 100.0}, 2: {2: 80.0, 3: 130.0}}
        plan = optimize([1, 2, 3], prices, self.RULES, max_stores=2)
        assert 1 in plan["stores"] and 2 in plan["stores"]
        assert plan["savings"] >= 0

    def test_empty_basket(self):
        plan = optimize([], self.PRICES, self.RULES)
        assert plan["total"] == 0.0
        assert plan["stores"] == []

    def test_reports_missing_items(self):
        prices = {1: {1: 94.99}}
        plan = optimize([1, 999], prices, self.RULES, max_stores=1)
        assert 999 in plan["missing"]
