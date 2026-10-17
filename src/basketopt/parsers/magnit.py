"""Parser for magnit.ru product pages.

Magnit renders each product page as a Nuxt payload: a single
``<script type="application/json">`` whose top-level value is a list.  Scalar
values are stored indirectly — a field holds an *index* into that list, and the
real value lives at that index.  An integer that is out of range is treated as a
literal number (this is how prices in kopecks are encoded).  ``_resolve`` walks
that indirection, so callers get plain Python values.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from urllib import error as urlerror
from urllib import request as urlrequest

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

_SCRIPT_RE = re.compile(r'<script[^>]*type="application/json"[^>]*>(.*?)</script>', re.S)
_H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.S)
_TAG_RE = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class MagnitProduct:
    """A single product scraped from magnit.ru."""

    name: str
    price_rub: float  # current price in rubles
    old_price_rub: float | None = None  # price before discount, if any
    discount_percent: int | None = None
    promo_end: str | None = None
    url: str = ""


def _resolve(payload: list, value, seen: set[int] | None = None) -> object:
    """Resolve a devalue reference to its concrete value."""
    if seen is None:
        seen = set()
    if isinstance(value, int) and 0 <= value < len(payload) and value not in seen:
        seen.add(value)
        return _resolve(payload, payload[value], seen)
    return value


def _find_product(payload: list) -> dict | None:
    """Locate the main product object inside the Nuxt payload."""
    for item in payload:
        if isinstance(item, dict) and "name" in item and "price" in item:
            return item
    return None


def parse_product_html(html: str) -> MagnitProduct:
    """Parse a Magnit product page into a :class:`MagnitProduct`.

    Raises ``ValueError`` if the page does not contain a parseable product.
    """
    scripts = _SCRIPT_RE.findall(html)
    if not scripts:
        raise ValueError("no application/json payload found on the page")
    payload = json.loads(max(scripts, key=len))

    product = _find_product(payload)
    if product is None:
        raise ValueError("product object not found in the payload")

    name = _resolve(payload, product.get("name"))
    if not isinstance(name, str) or not name.strip():
        match = _H1_RE.search(html)
        name = _TAG_RE.sub("", match.group(1)).strip() if match else ""

    price_raw = _resolve(payload, product.get("price"))
    if not isinstance(price_raw, int):
        raise ValueError(f"unexpected price value: {price_raw!r}")
    price_rub = price_raw / 100.0

    promo = _resolve(payload, product.get("promotion"))
    old_price_rub: float | None = None
    discount_percent: int | None = None
    promo_end: str | None = None
    if isinstance(promo, dict):
        old_raw = _resolve(payload, promo.get("oldPrice"))
        if isinstance(old_raw, int):
            old_price_rub = old_raw / 100.0
        dp = _resolve(payload, promo.get("discountPercent"))
        if isinstance(dp, int):
            discount_percent = dp
        pe = _resolve(payload, promo.get("endDate"))
        if isinstance(pe, str):
            promo_end = pe

    url = ""
    page_url = _resolve(payload, product.get("pageUrl"))
    if isinstance(page_url, str):
        url = page_url

    return MagnitProduct(
        name=name.strip(),
        price_rub=price_rub,
        old_price_rub=old_price_rub,
        discount_percent=discount_percent,
        promo_end=promo_end,
        url=url,
    )


def fetch_product(url: str, *, retries: int = 3, delay: float = 2.0) -> MagnitProduct:
    """Fetch and parse a Magnit product page, retrying on transient errors."""
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            req = urlrequest.Request(
                url, headers={"User-Agent": USER_AGENT, "Accept-Language": "ru"}
            )
            with urlrequest.urlopen(req, timeout=20) as resp:
                html = resp.read().decode("utf-8")
            product = parse_product_html(html)
            # keep URL on the result even though parse_product_html only sees HTML
            return MagnitProduct(
                name=product.name,
                price_rub=product.price_rub,
                old_price_rub=product.old_price_rub,
                discount_percent=product.discount_percent,
                promo_end=product.promo_end,
                url=url,
            )
        except (urlerror.URLError, urlerror.HTTPError, TimeoutError, OSError, ValueError) as exc:
            last_exc = exc
            if attempt < retries - 1:
                time.sleep(delay * (attempt + 1))
    raise last_exc if last_exc is not None else RuntimeError("fetch failed")
