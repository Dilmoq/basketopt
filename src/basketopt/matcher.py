"""Fuzzy matching of raw store product names to canonical items."""

from __future__ import annotations

import re
from difflib import SequenceMatcher

# Tokens that carry little meaning for matching.
_STOPWORDS = {"г", "мл", "л", "кг", "шт", "уп", "упак", "по", "и", "с", "в"}


def normalize(name: str) -> str:
    """Lower-case, unify units and punctuation."""
    s = name.lower().replace("ё", "е")
    s = re.sub(r"(\d)\s*(г|мл|л|кг|шт)\b", r"\1\2", s)
    s = re.sub(r"[^a-zа-я0-9%.,]+", " ", s)
    return " ".join(s.split())


def tokens(name: str) -> list[str]:
    return [t for t in normalize(name).split() if t not in _STOPWORDS and len(t) > 1]


def score(raw: str, canonical: str) -> float:
    """Token-overlap + sequence similarity, in [0, 1]."""
    t_raw = tokens(raw)
    t_can = tokens(canonical)
    if not t_raw or not t_can:
        return 0.0
    overlap = len(set(t_raw) & set(t_can)) / max(len(set(t_raw)), len(set(t_can)))
    seq = SequenceMatcher(None, normalize(raw), normalize(canonical)).ratio()
    return 0.6 * overlap + 0.4 * seq


def best_match(raw: str, candidates: list[tuple[int, str]], threshold: float = 0.75):
    """Return (item_id, canonical_name, score) for the best candidate or None."""
    best = None  # (score, item_id, canonical)
    for item_id, canonical in candidates:
        s = score(raw, canonical)
        if best is None or s > best[0]:
            best = (s, item_id, canonical)
    if best is None or best[0] < threshold:
        return None
    return best[1], best[2], best[0]
