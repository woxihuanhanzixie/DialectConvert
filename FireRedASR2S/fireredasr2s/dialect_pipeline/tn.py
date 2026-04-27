from __future__ import annotations

import re

import cn2an


TIME_RE = re.compile(r"([01]?\d|2[0-3]):([0-5]\d)")
MONEY_RE = re.compile(r"(\d+(?:\.\d+)?)\s*元")
PERCENT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%")
NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")
PUNC_RE = re.compile(r"[。！？；;!?]")


def normalize_text(text: str) -> str:
    x = text.strip()
    x = _normalize_time(x)
    x = _normalize_money(x)
    x = _normalize_percent(x)
    x = _normalize_number(x)
    return x


def _normalize_time(text: str) -> str:
    def repl(m: re.Match[str]) -> str:
        h = int(m.group(1))
        mm = int(m.group(2))
        if mm == 0:
            return f"{cn2an.an2cn(h)}点"
        return f"{cn2an.an2cn(h)}点{cn2an.an2cn(mm)}分"

    return TIME_RE.sub(repl, text)


def _normalize_money(text: str) -> str:
    def repl(m: re.Match[str]) -> str:
        num = m.group(1)
        if "." in num:
            integer, decimal = num.split(".", 1)
            integer_cn = cn2an.an2cn(integer)
            decimal_cn = "".join(cn2an.an2cn(c) for c in decimal if c.isdigit())
            return f"{integer_cn}点{decimal_cn}元"
        return f"{cn2an.an2cn(num)}元"

    return MONEY_RE.sub(repl, text)


def _normalize_percent(text: str) -> str:
    def repl(m: re.Match[str]) -> str:
        num = m.group(1)
        if "." in num:
            integer, decimal = num.split(".", 1)
            integer_cn = cn2an.an2cn(integer)
            decimal_cn = "".join(cn2an.an2cn(c) for c in decimal if c.isdigit())
            return f"百分之{integer_cn}点{decimal_cn}"
        return f"百分之{cn2an.an2cn(num)}"

    return PERCENT_RE.sub(repl, text)


def _normalize_number(text: str) -> str:
    def repl(m: re.Match[str]) -> str:
        num = m.group(0)
        if "." in num:
            integer, decimal = num.split(".", 1)
            integer_cn = cn2an.an2cn(integer)
            decimal_cn = "".join(cn2an.an2cn(c) for c in decimal if c.isdigit())
            return f"{integer_cn}点{decimal_cn}"
        return cn2an.an2cn(num)

    return NUMBER_RE.sub(repl, text)


def prepare_text_for_llm(text: str) -> str:
    """TN + punctuation normalization for better LLM rewrite quality."""
    x = normalize_text(text)
    x = x.replace("，", ",").replace("。", ".").replace("！", "!").replace("？", "?")
    x = re.sub(r"\s+", "", x)
    # Heuristic pre-segmentation for ASR text without punctuation.
    if not PUNC_RE.search(x):
        x = _insert_soft_punc(x)
    # Unify punctuation for downstream split/merge.
    x = x.replace(",", "，").replace(".", "。").replace("!", "！").replace("?", "？")
    return x


def prepare_reviewed_text_for_rewrite(text: str) -> str:
    """Light normalization for reviewed ASR text.

    Keep reviewed sentence rhythm and filler words, only normalize explicit
    numeric expressions and obvious punctuation noise.
    """
    x = text.strip()
    x = re.sub(r"\s+", "", x)
    x = re.sub(r"[，,]{2,}", "，", x)
    x = re.sub(r"[。\.]{2,}", "。", x)
    x = normalize_text(x)
    x = x.replace(",", "，").replace(".", "。").replace("!", "！").replace("?", "？")
    return x


def split_sentences(text: str, max_len: int = 28) -> list[str]:
    x = text.strip()
    if not x:
        return []
    # First split by existing punctuation.
    parts = [p.strip() for p in re.split(r"[。！？；]", x) if p.strip()]
    out: list[str] = []
    for p in parts:
        if len(p) <= max_len:
            out.append(p)
            continue
        # Long segment fallback split.
        out.extend([s for s in _split_long_segment(p, max_len=max_len) if s])
    return out


def _insert_soft_punc(text: str) -> str:
    # Simple conjunction-based soft punctuation insertion for ASR run-on text.
    x = text
    for token in ["但是", "不过", "然后", "所以", "同样", "如果", "并且", "而且", "另外"]:
        x = x.replace(token, f"，{token}")
    # If still too long, add comma every N chars to reduce one-shot LLM drift.
    chunks = [x[i : i + 22] for i in range(0, len(x), 22)]
    return "，".join(chunks)


def _split_long_segment(seg: str, max_len: int = 28) -> list[str]:
    if len(seg) <= max_len:
        return [seg]
    # Prefer splitting near soft punctuation/conjunction markers.
    markers = ["，", "、", "但是", "然后", "所以", "并且", "如果", "同样"]
    res: list[str] = []
    cur = seg
    while len(cur) > max_len:
        cut = -1
        window = cur[: max_len + 8]
        for m in markers:
            idx = window.rfind(m)
            if idx > cut:
                cut = idx + (1 if m in ["，", "、"] else len(m))
        if cut <= 0:
            cut = max_len
        res.append(cur[:cut].strip("，、 "))
        cur = cur[cut:]
    if cur.strip("，、 "):
        res.append(cur.strip("，、 "))
    return res
