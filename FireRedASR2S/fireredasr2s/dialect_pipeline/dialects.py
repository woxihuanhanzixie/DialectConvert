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


def build_teacher_style_instruction(target_dialect: str, dialect_style: str = "") -> str:
    """Build the Qwen teacher style instruction for the selected dialect."""
    style = normalize_dialect_style(target_dialect, dialect_style)
    label = dialect_label(target_dialect, style)
    instructions = {
        ("yue", "guangdong_general"): (
            "用自然、连贯、口语化的广东通用粤语播报。保留原句语义，句间连接平滑，"
            "停顿轻一点，整体比普通朗读更顺，但不要把调试用的规则化文本当成最终成果。"
        ),
        ("yue", "hongkong_colloquial"): (
            "用自然、连贯、偏香港口语的粤语表达。保留原句语义，语气轻松，句间连接平滑，"
            "不要过度书面化，也不要额外扩写内容。"
        ),
        ("yue", "formal_safe"): (
            "用稳妥、清楚、易懂的粤语播报。优先保证语义准确和发音稳定，口语化程度适中，"
            "避免生硬词表替换或夸张语气。"
        ),
        ("sichuan", "sichuan_general"): (
            "用自然、稳妥、口语化的四川话风格播报。优先保证普通话语义准确迁移，"
            "语气亲切顺口，但不要承诺规则化方言文本就是最终听感。"
        ),
        ("minnan", "minnan_general"): (
            "用自然、稳妥、口语化的闽南语风格播报。优先保证普通话语义准确迁移，"
            "发音和节奏以最终 teacher 音频听感为准，不依赖简单词表替换。"
        ),
    }
    return instructions.get(
        (target_dialect, style),
        f"用自然、连贯、口语化的{label}风格播报。优先保证语义准确、发音稳定和停顿自然，最终以 teacher 音频听感为准。",
    )


def is_supported_dialect(target_dialect: str) -> bool:
    return target_dialect in SUPPORTED_DIALECTS
