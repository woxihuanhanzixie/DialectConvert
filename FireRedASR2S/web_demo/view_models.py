from __future__ import annotations

from pathlib import Path
from typing import Any


def _resolve_route(tts: dict[str, Any], route_name: str) -> dict[str, Any]:
    route = tts.get(route_name) or {}
    if route:
        return route
    if route_name in {"baseline", "gold_teacher"}:
        return {
            "route_name": "gold_teacher",
            "wav_path": tts.get("baseline_wav_path", ""),
            "tts_model": tts.get("baseline_tts_model", ""),
            "tts_voice": tts.get("baseline_tts_voice", ""),
            "error": tts.get("baseline_error", ""),
            "input_text": tts.get("baseline_tts_input_text", ""),
            "input_mode": tts.get("baseline_tts_input_mode", ""),
            "route_reason": "Gold Teacher 作为系统方言发音参考的兼容回退结果。",
        }
    return {
        "route_name": "voice_matched",
        "wav_path": "",
        "tts_model": "",
        "tts_voice": "",
        "error": "",
        "input_text": "",
        "input_mode": "teacher_audio_to_audio",
        "voice_clone_enabled": False,
        "voice_clone_provider": "",
        "speaker_similarity_priority": "high",
        "tts_fluency_mode": "allow_rate_adjust",
        "route_reason": "Voice Matched 结果尚未生成。",
    }


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    if total == 0:
        return {"total": 0, "tts_ok": 0, "tts_failed": 0, "avg_rewrite_latency_ms": 0.0, "avg_tts_latency_ms": 0.0}
    tts_ok = sum(1 for r in rows if not r.get("tts_error"))
    rewrite_lat = [float(r.get("llm_latency_ms", 0.0)) for r in rows]
    tts_lat = [float(r.get("tts_latency_ms", 0.0)) for r in rows if r.get("tts_latency_ms") is not None] or [0.0]
    return {
        "total": total,
        "tts_ok": tts_ok,
        "tts_failed": total - tts_ok,
        "avg_rewrite_latency_ms": round(sum(rewrite_lat) / max(1, len(rewrite_lat)), 2),
        "avg_tts_latency_ms": round(sum(tts_lat) / max(1, len(tts_lat)), 2),
    }


def build_eval_table(rows: list[dict[str, Any]]) -> list[list[Any]]:
    return [
        [
            row.get("uttid", ""),
            row.get("source_text", ""),
            row.get("yue_text", "") or row.get("dialect_text", ""),
            "OK" if not row.get("tts_error") else "FAIL",
            row.get("tts_wav_path", ""),
        ]
        for row in rows
    ]


def _route_label(route_name: str) -> str:
    return {
        "gold_teacher": "Gold Teacher",
        "voice_matched": "Voice Matched",
        "baseline": "Gold Teacher",
        "clone": "Voice Matched",
    }.get(route_name, route_name or "未知链路")


def _recommended_route_label(route_name: str) -> str:
    return {
        "gold_teacher": "Gold Teacher 方言音频",
        "voice_matched": "Voice Matched 音色迁移音频",
        "baseline": "Gold Teacher 方言音频",
        "clone": "Voice Matched 音色迁移音频",
    }.get(route_name, route_name or "未知音频")


def _input_mode_label(mode: str) -> str:
    return {
        "review_text": "审查后文本",
        "semantic_text": "语义普通话文本",
        "dialect_text": "方言发声文本",
        "pronunciation_text": "发音转写文本",
        "prosody_text": "韵律润色文本",
        "teacher_audio_to_audio": "Gold Teacher 音频到音频",
        "dialect_text_with_cloned_voice": "方言文本 + 复刻音色",
        "semantic_text_with_cloned_voice": "Qwen Text Clone 对照项",
    }.get(mode, mode or "未知")


def _ref_source_label(ref_source: str) -> str:
    if ref_source == "input_audio_auto":
        return "主音频自动复用"
    if ref_source == "uploaded_ref":
        return "单独上传参考音频"
    return "无"


def _escape_markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def _escape_html(value: Any) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _highlight_terms(text: str, terms: list[str]) -> str:
    highlighted = _escape_html(text)
    for term in sorted({term for term in terms if term}, key=len, reverse=True):
        safe_term = _escape_html(term)
        highlighted = highlighted.replace(safe_term, f"<mark>{safe_term}</mark>")
    return highlighted


def build_cultural_cards_markdown(result: dict[str, Any]) -> str:
    rewrite = result.get("rewrite") or {}
    cards = rewrite.get("cultural_cards") or []
    if not cards:
        return "### 文化百科卡片\n暂无命中文化百科卡片。"
    matched_terms: list[str] = []
    for card in cards:
        matched_terms.extend(card.get("matched_terms") or [card.get("term", "")])
    terms = rewrite.get("cultural_card_terms") or [card.get("term", "") for card in cards]
    semantic_text = rewrite.get("semantic_text") or rewrite.get("dialect_text") or ""
    lines = [
        "### 文化百科卡片",
        f"命中片段：{_highlight_terms(semantic_text, matched_terms)}",
        " ".join(f"<mark>{_escape_html(term)}</mark>" for term in terms if term),
    ]
    for card in cards:
        matched_terms = "、".join(card.get("matched_terms") or [])
        source_label = card.get("source_label") or "资料整理"
        source_url = card.get("source_url") or ""
        source = f"[{source_label}]({source_url})" if source_url else source_label
        lines.extend(
            [
                "",
                f"**{card.get('term') or '方言词'}**",
                f"- 命中：{matched_terms or card.get('term') or '无'}",
                f"- 词义：{card.get('meaning') or '无'}",
                f"- 文化说明：{card.get('cultural_note') or '无'}",
                f"- 例句：{card.get('usage_example') or '无'}",
                f"- 语体：{card.get('register') or '无'}",
                f"- 来源：{source}",
            ]
        )
    return "\n".join(lines)


def _hit_count(items: Any) -> int:
    if not items:
        return 0
    if isinstance(items, list):
        return len(items)
    if isinstance(items, dict):
        return len(items)
    return 0


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_percent(value: Any) -> str:
    n = _number(value)
    if n is None:
        return "暂无"
    if n <= 1:
        n *= 100
    return f"{n:.1f}%"


def _format_ms(value: Any) -> str:
    n = _number(value)
    if n is None:
        return "暂无"
    return f"{n:.1f} ms"


def _pick_first_number(*values: Any) -> float | None:
    for value in values:
        n = _number(value)
        if n is not None:
            return n
    return None


def _rag_hits(rewrite: dict[str, Any]) -> list[Any]:
    hits: list[Any] = []
    for key in ("rag_hits", "pronunciation_rag_hits"):
        value = rewrite.get(key)
        if isinstance(value, list):
            hits.extend(value)
    return hits


def _rag_hit_rate(rewrite: dict[str, Any], rag_hit_count: int) -> str:
    explicit = _pick_first_number(
        rewrite.get("rag_hit_rate"),
        rewrite.get("pronunciation_rag_hit_rate"),
        rewrite.get("rag_recall_rate"),
    )
    if explicit is not None:
        return _format_percent(explicit)
    query_count = _pick_first_number(
        rewrite.get("rag_query_count"),
        rewrite.get("pronunciation_rag_query_count"),
        rewrite.get("rag_total"),
    )
    if query_count and query_count > 0:
        return _format_percent(rag_hit_count / query_count)
    if rag_hit_count > 0:
        return "已命中"
    return "暂无"


def _rag_latency(rewrite: dict[str, Any]) -> str:
    return _format_ms(
        _pick_first_number(
            rewrite.get("rag_latency_ms"),
            rewrite.get("pronunciation_rag_latency_ms"),
            rewrite.get("rag_elapsed_ms"),
        )
    )


def _rag_similarity(rewrite: dict[str, Any], hits: list[Any]) -> str:
    explicit = _pick_first_number(
        rewrite.get("semantic_similarity"),
        rewrite.get("rag_semantic_similarity"),
        rewrite.get("rag_avg_similarity"),
        rewrite.get("rag_top_score"),
    )
    if explicit is not None:
        return f"{explicit:.3f}"
    scores = []
    for hit in hits:
        if not isinstance(hit, dict):
            continue
        score = _pick_first_number(hit.get("semantic_similarity"), hit.get("similarity"), hit.get("score"))
        if score is not None:
            scores.append(score)
    if scores:
        return f"{max(scores):.3f}"
    return "暂无"


def build_result_stats_markdown(result: dict[str, Any]) -> str:
    rewrite = result.get("rewrite") or {}
    pronunciation_count = _hit_count(rewrite.get("pronunciation_rule_hits"))
    prosody_count = _hit_count(rewrite.get("prosody_rule_hits"))
    rag_hits = _rag_hits(rewrite)
    rag_count = len(rag_hits)
    final_count = pronunciation_count + prosody_count + rag_count
    return "\n".join(
        [
            "### 规则命中统计",
            (
                f"<small>最终命中次数：{final_count} 次 | "
                f"发音规则：{pronunciation_count} | 韵律规则：{prosody_count} | RAG：{rag_count}</small>"
            ),
            "### RAG 看板",
            (
                f"<small>命中率：{_rag_hit_rate(rewrite, rag_count)} | "
                f"耗时：{_rag_latency(rewrite)} | "
                f"语义相似度：{_rag_similarity(rewrite, rag_hits)}</small>"
            ),
        ]
    )


def build_recommendation_markdown(result: dict[str, Any]) -> str:
    tts = result.get("tts") or {}
    gap_summary = tts.get("gap_summary") or {}
    voice_match_summary = tts.get("voice_match_summary") or {}
    teacher_route = _resolve_route(tts, "gold_teacher")
    voice_matched_route = _resolve_route(tts, "voice_matched")
    recommended_route = tts.get("recommended_main_output") or gap_summary.get("recommended_route") or "gold_teacher"
    return "\n".join(
        [
            build_result_stats_markdown(result),
            "### 试听建议",
            f"- 推荐先听：{_recommended_route_label(recommended_route)}",
            "- 试听顺序：先听 Gold Teacher 确认方言发音，再听 Voice Matched 判断音色迁移。",
            f"- 推荐策略：{voice_match_summary.get('recommendation_reason') or gap_summary.get('recommended_strategy') or '无'}",
            f"- 推荐原因：{gap_summary.get('recommended_reason') or '无'}",
            f"- Gold Teacher 输入层：{_input_mode_label(teacher_route.get('input_mode') or '')}",
            f"- Voice Matched 输入层：{_input_mode_label(voice_matched_route.get('input_mode') or '')}",
        ]
    )


def build_text_compare_markdown(result: dict[str, Any]) -> str:
    asr = result.get("asr") or {}
    review = result.get("review") or {}
    rewrite = result.get("rewrite") or {}
    tts = result.get("tts") or {}
    teacher_route = _resolve_route(tts, "gold_teacher")
    voice_matched_route = _resolve_route(tts, "voice_matched")
    rows = [
        ("原始 ASR", asr.get("punc_text") or asr.get("text") or "无"),
        ("审查后语义普通话", review.get("asr_reviewed_text") or "无"),
        ("方言发声文本", rewrite.get("dialect_text") or "无"),
        ("发音转写文本", rewrite.get("pronunciation_text") or "无"),
        ("韵律润色文本", rewrite.get("prosody_text") or "无"),
        (f"Gold Teacher 输入文本（{_input_mode_label(teacher_route.get('input_mode') or '')}）", teacher_route.get("input_text") or "无"),
        (f"Voice Matched Source（{_input_mode_label(voice_matched_route.get('input_mode') or '')}）", voice_matched_route.get("input_text") or "Gold Teacher 音频"),
    ]
    lines = ["### 文本与音频路由对比", "| 区域 | 内容 |", "| --- | --- |"]
    for label, value in rows:
        lines.append(f"| {label} | {_escape_markdown_cell(value)} |")
    return "\n".join(lines)


def build_gap_summary_markdown(result: dict[str, Any]) -> str:
    tts = result.get("tts") or {}
    gap_summary = tts.get("gap_summary") or {}
    voice_match_summary = tts.get("voice_match_summary") or {}
    recommended_label = _recommended_route_label(tts.get("recommended_main_output") or gap_summary.get("recommended_route") or "gold_teacher")
    return "\n".join(
        [
            "### 差距摘要",
            f"- Teacher vs Voice Matched 内容差异：{gap_summary.get('content_diff') or 'Voice Matched 应继承 Gold Teacher 音频内容。'}",
            f"- Teacher vs Voice Matched 发音差异：{gap_summary.get('pronunciation_diff') or 'Voice Matched 不重新决定发音。'}",
            f"- Teacher vs Voice Matched 流畅度差异：{gap_summary.get('fluency_diff') or '无'}",
            f"- 路由摘要：{gap_summary.get('route_summary') or '无'}",
            f"- 处理分工：{gap_summary.get('processing_split') or 'Gold Teacher 决定怎么说，Voice Matched 决定像谁说。'}",
            f"- Voice Matched 可用：{'是' if voice_match_summary.get('voice_matched_available') else '否'}",
            f"- Voice Matched Provider：{voice_match_summary.get('voice_match_provider') or '无'}",
            f"- Voice Matched 错误：{voice_match_summary.get('voice_match_error') or '无'}",
            f"- 当前推荐：{recommended_label}",
        ]
    )


def build_route_cards_markdown(result: dict[str, Any]) -> tuple[str, str]:
    tts = result.get("tts") or {}
    teacher_route = _resolve_route(tts, "gold_teacher")
    voice_matched_route = _resolve_route(tts, "voice_matched")
    recommended_route = tts.get("recommended_main_output") or "gold_teacher"

    def _build(route: dict[str, Any]) -> str:
        route_name = route.get("route_name") or "gold_teacher"
        title = f"### {_route_label(route_name)}{'（推荐先听）' if route_name == recommended_route else ''}"
        return "\n".join(
            [
                title,
                f"- 输入层：{_input_mode_label(route.get('input_mode') or '')}",
                f"- 输入/Source：{route.get('input_text') or '无'}",
                f"- 路由说明：{route.get('route_reason') or '无'}",
                f"- 模型/Provider：{route.get('tts_model') or route.get('voice_clone_provider') or '无'}",
                f"- 音色：{route.get('tts_voice') or route.get('voice_clone_provider') or '无'}",
                f"- 错误：{route.get('error') or '无'}",
            ]
        )

    return _build(teacher_route), _build(voice_matched_route)


def human_review_markdown(result: dict[str, Any]) -> str:
    asr = result.get("asr") or {}
    review = result.get("review") or {}
    rewrite = result.get("rewrite") or {}
    tts = result.get("tts") or {}
    teacher_route = _resolve_route(tts, "gold_teacher")
    voice_matched_route = _resolve_route(tts, "voice_matched")
    gap_summary = tts.get("gap_summary") or {}
    voice_match_summary = tts.get("voice_match_summary") or {}
    source_audio = result.get("source_audio") or {}
    frontend = source_audio.get("audio_frontend") or {}
    work_audio = frontend.get("work_audio") or {}
    ref_audio = source_audio.get("voice_clone_ref_audio") or {}
    ref_frontend = ref_audio.get("audio_frontend") or {}
    ref_source_label = _ref_source_label(ref_audio.get("source") or "none")
    return "\n".join(
        [
            "### 人工审核对照",
            f"- 输入语言：{result.get('input_lang') or '未知'}",
            f"- 原始 ASR：{asr.get('punc_text') or asr.get('text') or '无'}",
            f"- 审查后语义普通话：{review.get('asr_reviewed_text') or '无'}",
            f"- Pivot 中文：{result.get('pivot_text_zh') or rewrite.get('pivot_text_zh') or '无'}",
            f"- 方言发声文本：{rewrite.get('dialect_text') or '无'}",
            f"- 发音转写文本：{rewrite.get('pronunciation_text') or '无'}",
            f"- 韵律润色文本：{rewrite.get('prosody_text') or '无'}",
            f"- 目标方言：{rewrite.get('target_dialect') or 'yue'}",
            f"- 方言风格：{rewrite.get('dialect_style') or 'guangdong_general'}",
            f"- 工作音频质量分：{work_audio.get('quality_score', '无')}",
            f"- 音色迁移：{'是' if tts.get('voice_clone_enabled') else '否'}",
            f"- 参考来源：{ref_source_label}",
            f"- 参考处理：{ref_audio.get('frontend_mode') or '无'}",
            f"- 参考拼接片段：{ref_frontend.get('speech_segment_count', 0)}",
            f"- 参考拼接时长：{ref_frontend.get('concat_duration_s', '无')}",
            f"- Gold Teacher 模型：{teacher_route.get('tts_model') or '无'}",
            f"- Gold Teacher 音色：{teacher_route.get('tts_voice') or '无'}",
            f"- Gold Teacher 输入模式：{_input_mode_label(teacher_route.get('input_mode') or '')}",
            f"- Gold Teacher 输入文本：{teacher_route.get('input_text') or '无'}",
            f"- Gold Teacher 音频文件：{Path(teacher_route.get('wav_path', '')).name if teacher_route.get('wav_path') else '无'}",
            f"- Voice Matched Provider：{voice_matched_route.get('voice_clone_provider') or '无'}",
            f"- Voice Matched 输入模式：{_input_mode_label(voice_matched_route.get('input_mode') or '')}",
            f"- Voice Matched Source：{voice_matched_route.get('input_text') or teacher_route.get('wav_path') or '无'}",
            f"- Voice Matched 音频文件：{Path(voice_matched_route.get('wav_path', '')).name if voice_matched_route.get('wav_path') else '无'}",
            f"- Voice Matched 错误：{voice_matched_route.get('error') or '无'}",
            f"- 路由摘要：{gap_summary.get('route_summary') or '无'}",
            f"- 推荐试听：{tts.get('recommended_main_output') or gap_summary.get('recommended_route') or 'gold_teacher'}",
            f"- 推荐策略：{voice_match_summary.get('recommendation_reason') or gap_summary.get('recommended_strategy') or '无'}",
        ]
    )
