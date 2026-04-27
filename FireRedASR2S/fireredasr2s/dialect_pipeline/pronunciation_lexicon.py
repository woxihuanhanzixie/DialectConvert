from __future__ import annotations

from typing import Any


def get_pronunciation_rules(target_dialect: str, dialect_style: str) -> list[dict[str, Any]]:
    if target_dialect != "yue":
        return []
    base = [
        _rule("梅西", "美斯", notes="体育专名按粤语常用叫法读", category="named_entity"),
        _rule("库里", "居里", notes="体育专名按粤语常用叫法读", category="named_entity"),
        _rule("足球", "足球", notes="保留词面，交给上下文和粤语语境处理", priority=10, category="domain_term"),
        _rule("同样", "一样", notes="避免按普通话直读", category="function_word"),
        _rule("这样", "咁样", notes="改为更常见的粤语口语写法", category="function_word"),
        _rule("这个", "呢个", notes="改为更常见的粤语口语写法", category="function_word"),
        _rule("那个", "嗰个", notes="改为更常见的粤语口语写法", category="function_word"),
        _rule("什么", "咩", notes="改为更常见的粤语口语写法", category="function_word"),
        _rule("为什么", "点解", notes="改为更常见的粤语口语写法", category="function_word"),
        _rule("不是", "唔系", notes="改为更常见的粤语口语写法", category="function_word"),
        _rule("没有", "冇", notes="改为更常见的粤语口语写法", category="function_word"),
        _rule("然后", "跟住", notes="改为更口语化的连接词", category="connector"),
    ]
    if dialect_style == "formal_safe":
        return [r for r in base if r["source"] not in {"然后"}]
    return base


def _rule(
    source: str,
    pronunciation_form: str,
    *,
    notes: str = "",
    priority: int = 100,
    category: str = "generic",
) -> dict[str, Any]:
    return {
        "source": source,
        "semantic_form": source,
        "pronunciation_form": pronunciation_form,
        "target_dialect": "yue",
        "dialect_style": "guangdong_general",
        "priority": priority,
        "category": category,
        "notes": notes,
    }
