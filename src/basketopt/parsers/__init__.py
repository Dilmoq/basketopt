"""Store parsers: turn a store's product page into a structured product."""

from .magnit import MagnitProduct, fetch_product, parse_product_html

__all__ = ["MagnitProduct", "fetch_product", "parse_product_html"]
