import json
from pathlib import Path

from app.rag import GraphDialectFact, set_dialect_graph_provider
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


def test_cantonese_competition_context_retrieves_formal_terms():
    context = retrieve_dialect_knowledge("各位评委老师，我们很荣幸参加这次比赛决赛", "cantonese", top_k=8)

    assert "评委老师" in context
    assert "好荣幸" in context
    assert "今次" in context or "呢次" in context


def test_optional_graph_provider_can_extend_rag_context():
    class FakeGraphProvider:
        def query(self, source_text, dialect, top_k=5):
            assert source_text == "保护方言"
            assert dialect == "cantonese"
            return [
                GraphDialectFact(
                    source="方言保护",
                    relation="has_goal",
                    target="承传乡下话",
                    note="文化传承语境",
                )
            ]

    set_dialect_graph_provider(FakeGraphProvider())
    try:
        context = retrieve_dialect_knowledge("保护方言", "cantonese")
    finally:
        set_dialect_graph_provider(None)

    assert "以下是该方言知识图谱的语义关系参考" in context
    assert "方言保护" in context
    assert "has_goal" in context
    assert "承传乡下话" in context
