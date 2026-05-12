from __future__ import annotations

from typing import Any


def get_pronunciation_rules(target_dialect: str, dialect_style: str) -> list[dict[str, Any]]:
    if target_dialect == "yue":
        return _yue_rules(dialect_style)
    if target_dialect == "sichuan":
        return _sichuan_rules(dialect_style)
    if target_dialect == "minnan":
        return _minnan_rules(dialect_style)
    return []


def _yue_rules(dialect_style: str) -> list[dict[str, Any]]:
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


def _sichuan_rules(dialect_style: str) -> list[dict[str, Any]]:
    return [
        _rule("非常", "硬是", target_dialect="sichuan", dialect_style=dialect_style, category="degree_word", notes="四川话常用程度副词"),
        _rule("很", "得很", target_dialect="sichuan", dialect_style=dialect_style, priority=20, category="degree_word", notes="基础演示口语化"),
        _rule("什么", "啥子", target_dialect="sichuan", dialect_style=dialect_style, category="function_word", notes="疑问词口语化"),
        _rule("为什么", "为啥子", target_dialect="sichuan", dialect_style=dialect_style, category="function_word", notes="疑问词口语化"),
        _rule("没有", "莫得", target_dialect="sichuan", dialect_style=dialect_style, category="function_word", notes="否定词口语化"),
        _rule("可以", "要得", target_dialect="sichuan", dialect_style=dialect_style, category="function_word", notes="高频应答词"),
        _rule("这样", "啷个", target_dialect="sichuan", dialect_style=dialect_style, category="function_word", notes="高频指代词"),
        _rule("事情", "事", target_dialect="sichuan", dialect_style=dialect_style, category="domain_term", notes="降低书面感"),
    ]


def _minnan_rules(dialect_style: str) -> list[dict[str, Any]]:
    return [
        _rule("非常", "真正足", target_dialect="minnan", dialect_style=dialect_style, category="degree_word", notes="闽南语常用程度表达"),
        _rule("很", "足", target_dialect="minnan", dialect_style=dialect_style, priority=20, category="degree_word", notes="基础演示口语化"),
        _rule("什么", "啥物", target_dialect="minnan", dialect_style=dialect_style, category="function_word", notes="疑问词口语化"),
        _rule("为什么", "为啥物", target_dialect="minnan", dialect_style=dialect_style, category="function_word", notes="疑问词口语化"),
        _rule("不是", "毋是", target_dialect="minnan", dialect_style=dialect_style, category="function_word", notes="否定词口语化"),
        _rule("没有", "无", target_dialect="minnan", dialect_style=dialect_style, category="function_word", notes="否定词口语化"),
        _rule("可以", "会使", target_dialect="minnan", dialect_style=dialect_style, category="function_word", notes="高频应答词"),
        _rule("这样", "按呢", target_dialect="minnan", dialect_style=dialect_style, category="function_word", notes="高频指代词"),
        _rule("事情", "代志", target_dialect="minnan", dialect_style=dialect_style, category="domain_term", notes="常见词替换"),
    ]


def _rule(
    source: str,
    pronunciation_form: str,
    *,
    target_dialect: str = "yue",
    dialect_style: str = "guangdong_general",
    notes: str = "",
    priority: int = 100,
    category: str = "generic",
) -> dict[str, Any]:
    return {
        "source": source,
        "semantic_form": source,
        "pronunciation_form": pronunciation_form,
        "target_dialect": target_dialect,
        "dialect_style": dialect_style,
        "priority": priority,
        "category": category,
        "notes": notes,
    }
