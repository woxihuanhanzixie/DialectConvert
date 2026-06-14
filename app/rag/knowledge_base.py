"""Dialect knowledge base: load, index and query dialect-specific lexical entries.

Each .json file under data/ is a list of objects with the shape:

    {
      "keyword": "年轻人",            # Mandarin keyword / phrase
      "dialect_expression": "后生仔", # Natural dialect equivalent
      "category": "日常",             # Semantic category
      "usage_note": "口语常用，含亲切感",
      "context": "指年轻人、年轻一代"
    }

The knowledge base is loaded lazily and cached in memory.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_DATA_DIR = Path(__file__).resolve().parent / "data"

_DIALECT_FILES = {
    "cantonese": "cantonese.json",
    "sichuanese": "sichuanese.json",
    "hokkien": "hokkien.json",
}

_cache: dict[str, list[dict[str, str]]] = {}


def _load(dialect: str) -> list[dict[str, str]]:
    if dialect in _cache:
        return _cache[dialect]

    filename = _DIALECT_FILES.get(dialect)
    if not filename:
        _cache[dialect] = []
        return []

    path = _DATA_DIR / filename
    if not path.is_file():
        _cache[dialect] = []
        return []

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            _cache[dialect] = data
        else:
            _cache[dialect] = []
    except (json.JSONDecodeError, OSError):
        _cache[dialect] = []

    return _cache[dialect]


def query(dialect: str, keywords: list[str], top_k: int = 5) -> list[dict[str, str]]:
    """Return top-k knowledge entries whose keyword field overlaps with *keywords*.

    Matching is case-insensitive and uses substring containment so that partial
    overlaps (e.g. "变" against "变成") still surface relevant entries.
    """
    entries = _load(dialect)
    if not entries or not keywords:
        return []

    scored: list[tuple[int, dict[str, str]]] = []
    lowered = [k.lower() for k in keywords]

    for entry in entries:
        entry_kw = (entry.get("keyword") or "").lower()
        if not entry_kw:
            continue
        score = 0
        for kw in lowered:
            if kw in entry_kw or entry_kw in kw:
                score += 1
        if score > 0:
            scored.append((score, entry))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [entry for _, entry in scored[:top_k]]


def entry_count(dialect: str) -> int:
    return len(_load(dialect))


def reload() -> None:
    """Clear cache so next query re-reads JSON files from disk."""
    _cache.clear()
