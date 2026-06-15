"""Extension point for future dialect knowledge graph retrieval.

The current RAG layer is JSON keyword retrieval. This module keeps the graph
boundary explicit so a later Neo4j, NetworkX, RDF, or service-backed provider
can be plugged in without changing the pipeline or LLM prompt caller.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, Sequence


@dataclass(frozen=True)
class GraphDialectFact:
    """A prompt-ready semantic relation from a dialect knowledge graph."""

    source: str
    relation: str
    target: str
    note: str = ""


class DialectGraphProvider(Protocol):
    """Provider protocol for semantic graph retrieval.

    Implementations should return the most relevant graph facts for the source
    Mandarin text and target dialect. They may use local graph files, NetworkX,
    Neo4j, RDF stores, or remote services behind this stable interface.
    """

    def query(self, source_text: str, dialect: str, top_k: int = 5) -> Sequence[GraphDialectFact | dict[str, Any]]:
        ...


_provider: DialectGraphProvider | None = None


def set_dialect_graph_provider(provider: DialectGraphProvider | None) -> None:
    """Register or clear the optional dialect graph provider."""

    global _provider
    _provider = provider


def query_graph_facts(source_text: str, dialect: str, top_k: int = 5) -> list[GraphDialectFact]:
    """Return graph facts from the registered provider, if one exists.

    Provider errors are intentionally isolated from the main conversion path:
    lexical RAG should continue working even when a future graph backend is
    offline or misconfigured.
    """

    if _provider is None:
        return []

    try:
        raw_facts = _provider.query(source_text, dialect, top_k=top_k)
    except Exception:
        return []

    facts: list[GraphDialectFact] = []
    for raw in raw_facts[:top_k]:
        fact = _coerce_fact(raw)
        if fact:
            facts.append(fact)
    return facts


def _coerce_fact(raw: GraphDialectFact | dict[str, Any]) -> GraphDialectFact | None:
    if isinstance(raw, GraphDialectFact):
        return raw
    if not isinstance(raw, dict):
        return None

    source = str(raw.get("source") or raw.get("concept") or raw.get("keyword") or "").strip()
    relation = str(raw.get("relation") or raw.get("predicate") or "related_to").strip()
    target = str(raw.get("target") or raw.get("dialect_expression") or raw.get("object") or "").strip()
    note = str(raw.get("note") or raw.get("usage_note") or raw.get("context") or "").strip()
    if not source or not relation or not target:
        return None
    return GraphDialectFact(source=source, relation=relation, target=target, note=note)
