import json
from pathlib import Path

from app.rag.retriever import retrieve_dialect_knowledge


DATA_DIR = Path(__file__).resolve().parents[1] / "app" / "rag" / "data"


def test_rag_data_files_are_valid_and_expanded():
    expected_minimums = {
        "cantonese.json": 70,
        "sichuanese.json": 70,
        "hokkien.json": 73,
    }

    for filename, minimum in expected_minimums.items():
        entries = json.loads((DATA_DIR / filename).read_text(encoding="utf-8"))
        assert len(entries) >= minimum
        assert all(entry.get("keyword") and entry.get("dialect_expression") for entry in entries)


def test_ai_unclear_demo_sentence_retrieves_dialect_context():
    source_text = "AI 就会有点不清楚"

    for dialect in ("cantonese", "sichuanese", "hokkien"):
        context = retrieve_dialect_knowledge(source_text, dialect, top_k=5)
        assert "AI" in context
        assert "不清楚" in context or "有点" in context
