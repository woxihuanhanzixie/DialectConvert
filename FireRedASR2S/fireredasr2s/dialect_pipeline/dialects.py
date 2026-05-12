from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DialectSpec:
    code: str
    label: str
    default_style: str
    style_labels: dict[str, str]


SUPPORTED_DIALECTS: dict[str, DialectSpec] = {
    "yue": DialectSpec(
        code="yue",
        label="粤语",
        default_style="guangdong_general",
        style_labels={
            "guangdong_general": "广东通用粤语",
            "hongkong_colloquial": "香港口语粤语",
            "formal_safe": "稳妥易懂粤语",
        },
    ),
    "sichuan": DialectSpec(
        code="sichuan",
        label="四川话",
        default_style="sichuan_general",
        style_labels={
            "sichuan_general": "四川话",
        },
    ),
    "minnan": DialectSpec(
        code="minnan",
        label="闽南语",
        default_style="minnan_general",
        style_labels={
            "minnan_general": "闽南语",
        },
    ),
}


def supported_dialect_codes() -> list[str]:
    return list(SUPPORTED_DIALECTS)


def normalize_dialect_style(target_dialect: str, dialect_style: str = "") -> str:
    spec = SUPPORTED_DIALECTS.get(target_dialect)
    if spec is None:
        return dialect_style
    if not dialect_style:
        return spec.default_style
    if dialect_style in spec.style_labels:
        return dialect_style
    return spec.default_style


def dialect_label(target_dialect: str, dialect_style: str = "") -> str:
    spec = SUPPORTED_DIALECTS.get(target_dialect)
    if spec is None:
        return "目标方言"
    style = normalize_dialect_style(target_dialect, dialect_style)
    return spec.style_labels.get(style, spec.label)


def is_supported_dialect(target_dialect: str) -> bool:
    return target_dialect in SUPPORTED_DIALECTS
