from __future__ import annotations

from typing import Iterable


def postprocess_dialect_text(text: str, *, target_dialect: str, dialect_style: str) -> str:
    value = text.strip()
    if not value:
        return value
    if target_dialect == "yue":
        value = _apply_replacements(value, _yue_rules(dialect_style))
    elif target_dialect == "sichuan":
        value = _apply_replacements(value, _sichuan_rules(dialect_style))
    elif target_dialect == "minnan":
        value = _apply_replacements(value, _minnan_rules(dialect_style))
    return value.strip()


def _apply_replacements(text: str, rules: Iterable[tuple[str, str]]) -> str:
    value = text
    for src, dst in rules:
        value = value.replace(src, dst)
    return value


def _yue_rules(dialect_style: str) -> list[tuple[str, str]]:
    common = [
        ("非常", "真系"),
        ("很重要", "好紧要"),
        ("重要嘅事", "紧要"),
        ("事情", "事"),
        ("造成", "搞到"),
        ("不可逆", "好难救返"),
        ("永久性嘅损伤", "伤到根"),
        ("冇得补救", "好难救返"),
        ("很难补救", "好难救返"),
        ("补救", "救返"),
        ("出现", "出咗"),
        ("但是", "但系"),
        ("并且", "同埋"),
        ("更多可能", "更多可能性"),
        ("这样", "咁样"),
        ("这个", "呢个"),
        ("那个", "嗰个"),
    ]
    if dialect_style == "formal_safe":
        return common + [("真系", "真系"), ("搞到", "令到")]
    if dialect_style == "hongkong_colloquial":
        return common + [("现在", "而家"), ("可以", "可以"), ("很", "好")]
    return common + [("现在", "而家"), ("很", "好")]


def _sichuan_rules(dialect_style: str) -> list[tuple[str, str]]:
    _ = dialect_style
    return [
        ("非常", "硬是"),
        ("很重要", "重要得很"),
        ("事情", "事"),
        ("出现", "冒出来"),
        ("造成", "整到"),
        ("不可逆", "不好补救"),
        ("很难补救", "不好补救"),
        ("补救", "补起"),
        ("这样", "啷个"),
        ("这个", "这个"),
        ("那个", "那个"),
        ("什么", "啥子"),
        ("为什么", "为啥子"),
        ("不是", "不是"),
        ("没有", "莫得"),
        ("然后", "然后嘛"),
        ("现在", "现在"),
        ("可以", "要得"),
    ]


def _minnan_rules(dialect_style: str) -> list[tuple[str, str]]:
    _ = dialect_style
    return [
        ("非常", "真正足"),
        ("很重要", "足重要"),
        ("事情", "代志"),
        ("出现", "出现"),
        ("造成", "害到"),
        ("不可逆", "袂好补救"),
        ("很难补救", "袂好补救"),
        ("补救", "补救"),
        ("这样", "按呢"),
        ("这个", "这项"),
        ("那个", "彼项"),
        ("什么", "啥物"),
        ("为什么", "为啥物"),
        ("不是", "毋是"),
        ("没有", "无"),
        ("然后", "然后阁"),
        ("现在", "今仔日"),
        ("可以", "会使"),
    ]
