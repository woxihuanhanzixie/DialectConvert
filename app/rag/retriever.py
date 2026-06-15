"""Lightweight keyword + TF-IDF retriever for dialect knowledge.

The retriever does NOT require any external embedding model or vector database.
It tokenises the source Mandarin text with jieba (if installed) or a simple
character-bigram fallback, matches tokens against the dialect knowledge base,
and returns a formatted prompt snippet ready to inject into the LLM rewrite call.
"""

from __future__ import annotations

import re

from .graph import query_graph_facts
from . import knowledge_base

try:
    import jieba

    _JIEBA = True
except ImportError:
    _JIEBA = False


def _tokenize(text: str) -> list[str]:
    """Tokenize Mandarin text into meaningful units."""
    text = re.sub(r"""[，。！？、；："'（）\s]+""", " ", text).strip()
    if not text:
        return []

    if _JIEBA:
        tokens = [w.strip() for w in jieba.cut(text) if len(w.strip()) >= 1]
    else:
        # Fallback: character bigrams + single characters for shorter texts.
        cleaned = text.replace(" ", "")
        tokens = []
        for i in range(len(cleaned) - 1):
            tokens.append(cleaned[i : i + 2])
        tokens.extend(list(cleaned))

    # Deduplicate while preserving order.
    seen: set[str] = set()
    result: list[str] = []
    for t in tokens:
        if t not in seen:
            seen.add(t)
            result.append(t)
    return result


def retrieve_dialect_knowledge(
    source_text: str,
    dialect: str,
    top_k: int = 5,
) -> str:
    """Return a prompt-ready dialect-knowledge snippet for the given source text.

    Returns an empty string when no relevant entries are found so that callers
    can unconditionally prepend/append the result to the LLM prompt.
    """
    if not source_text or not dialect:
        return ""

    tokens = _tokenize(source_text)
    entries = knowledge_base.query(dialect, tokens, top_k=top_k)
    graph_facts = query_graph_facts(source_text, dialect, top_k=top_k)

    if not entries and not graph_facts:
        return ""

    lines: list[str] = []
    if entries:
        lines.append("以下是该方言的正确表达参考（请优先使用）：")
        for e in entries:
            kw = e.get("keyword", "")
            dex = e.get("dialect_expression", "")
            note = e.get("usage_note", "")
            line = f"- 「{kw}」→ {dex}"
            if note:
                line += f"（{note}）"
            lines.append(line)

    if graph_facts:
        if lines:
            lines.append("")
        lines.append("以下是该方言知识图谱的语义关系参考：")
        for fact in graph_facts:
            line = f"- 「{fact.source}」--{fact.relation}-->「{fact.target}」"
            if fact.note:
                line += f"（{fact.note}）"
            lines.append(line)

    return "\n".join(lines)
