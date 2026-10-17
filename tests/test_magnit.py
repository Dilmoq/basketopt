"""Tests for the Magnit parser (no network)."""

import pathlib

import pytest

from basketopt.parsers.magnit import MagnitProduct, parse_product_html

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "magnit_product.html"


class TestParseProductHtml:
    def test_parses_name_and_price(self):
        html = FIXTURE.read_text(encoding="utf-8")
        product = parse_product_html(html)
        assert isinstance(product, MagnitProduct)
        assert "Молоко Простоквашино" in product.name
        assert product.price_rub == 94.99

    def test_no_promo_means_no_old_price(self):
        html = FIXTURE.read_text(encoding="utf-8")
        product = parse_product_html(html)
        # this particular product is not on promotion
        assert product.old_price_rub is None
        assert product.discount_percent is None

    def test_missing_payload_raises(self):
        with pytest.raises(ValueError):
            parse_product_html("<html><body>nothing here</body></html>")

    def test_url_is_parsed_from_page(self):
        html = FIXTURE.read_text(encoding="utf-8")
        product = parse_product_html(html)
        assert product.url.startswith("https://magnit.ru/product/")


class TestResolve:
    def test_resolve_handles_out_of_range_literal(self):
        # an integer larger than the payload length is a literal number
        from basketopt.parsers.magnit import _resolve

        payload = ["x", 42]
        assert _resolve(payload, 9999) == 9999
        assert _resolve(payload, 1) == 42
