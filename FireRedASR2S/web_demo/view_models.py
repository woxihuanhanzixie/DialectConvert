from __future__ import annotations

from pathlib import Path
from typing import Any


def _resolve_route(tts: dict[str, Any], route_name: str) -> dict[str, Any]:
    route = tts.get(route_name) or {}
    if route:
        return route
    fallback_map = {
        "gold_teacher": {
            "route_name": "gold_teacher",
            "wav_path": tts.get("baseline_wav_path", ""),
            "tts_model": tts.get("baseline_tts_model", ""),
            "tts_voice": tts.get("baseline_tts_voice", ""),
            "error": tts.get("baseline_error", ""),
            "input_text": tts.get("baseline_tts_input_text", ""),
            "input_mode": tts.get("baseline_tts_input_mode", ""),
            "route_reason": "gold teacher 作为系统粤语发音金标准的兼容回退结果。",
        },
        "legacy_text_clone": {
            "route_name": "legacy_text_clone",
            "wav_path": tts.get("wav_path", ""),
            "tts_model": tts.get("tts_model", ""),
            "tts_voice": tts.get("tts_voice", ""),
            "error": tts.get("error", ""),
            "input_text": tts.get("tts_input_text", ""),
            "input_mode": tts.get("tts_input_mode", ""),
            "voice_clone_enabled": tts.get("voice_clone_enabled", False),
            "voice_clone_provider": tts.get("voice_clone_provider", ""),
            "speaker_similarity_priority": tts.get("speaker_similarity_priority", "high"),
            "tts_fluency_mode": tts.get("tts_fluency_mode", "allow_rate_adjust"),
            "route_reason": "legacy 文本克隆链路的兼容回退结果。",
        },
        "voice_matched": {
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
            "route_reason": "voice matched 结果尚未生成。",
        },
    }
    if route_name == "baseline":
        return fallback_map["gold_teacher"]
    if route_name == "clone":
        return fallback_map["legacy_text_clone"]
    return fallback_map.get(route_name, {"route_name": route_name})


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    if total == 0:
        return {"total": 0, "tts_ok": 0, "tts_failed": 0, "avg_rewrite_latency_ms": 0.0, "avg_tts_latency_ms": 0.0}
    tts_ok = sum(1 for r in rows if not r.get("tts_error"))
    rewrite_lat = [float(r.get("llm_latency_ms", 0.0)) for r in rows]
    tts_lat = [float(r.get("tts_latency_ms", 0.0)) for r in rows if r.get("tts_latency_ms") is not None]
    if not tts_lat:
        tts_lat = [0.0 for _ in rows]
    return {
        "total": total,
        "tts_ok": tts_ok,
        "tts_failed": total - tts_ok,
        "avg_rewrite_latency_ms": round(sum(rewrite_lat) / max(1, len(rewrite_lat)), 2),
        "avg_tts_latency_ms": round(sum(tts_lat) / max(1, len(tts_lat)), 2),
    }


def build_eval_table(rows: list[dict[str, Any]]) -> list[list[Any]]:
    table: list[list[Any]] = []
    for row in rows:
        table.append(
            [
                row.get("uttid", ""),
                row.get("source_text", ""),
                row.get("yue_text", "") or row.get("dialect_text", ""),
                "OK" if not row.get("tts_error") else "FAIL",
                row.get("tts_wav_path", ""),
            ]
        )
    return table


def _route_label(route_name: str) -> str:
    mapping = {
        "gold_teacher": "Gold Teacher",
        "voice_matched": "Voice Matched",
        "legacy_text_clone": "旧文本克隆",
        "baseline": "Gold Teacher",
        "clone": "旧文本克隆",
    }
    return mapping.get(route_name, route_name or "未知链路")


def _recommended_route_label(route_name: str) -> str:
    mapping = {
        "gold_teacher": "Gold Teacher 音频",
        "voice_matched": "Voice Matched 音频",
        "legacy_text_clone": "旧文本克隆音频",
        "baseline": "Gold Teacher 音频",
        "clone": "旧文本克隆音频",
    }
    return mapping.get(route_name, route_name or "未知音频")


def _input_mode_label(mode: str) -> str:
    mapping = {
        "review_text": "审查后文本",
        "semantic_text": "语义转写文本",
        "pronunciation_text": "发音转写文本",
        "prosody_text": "韵律润色文本",
        "teacher_audio_to_audio": "teacher 音频到音频",
    }
    return mapping.get(mode, mode or "未知")


def _ref_source_label(ref_source: str) -> str:
    if ref_source == "input_audio_auto":
        return "主音频自动复用"
    if ref_source == "uploaded_ref":
        return "单独上传参考音频"
    return "无"


def _escape_markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def build_recommendation_markdown(result: dict[str, Any]) -> str:
    tts = result.get("tts") or {}
    gap_summary = tts.get("gap_summary") or {}
    voice_match_summary = tts.get("voice_match_summary") or {}
    teacher_route = _resolve_route(tts, "gold_teacher")
    voice_matched_route = _resolve_route(tts, "voice_matched")
    legacy_clone_route = _resolve_route(tts, "legacy_text_clone")
    recommended_route = tts.get("recommended_main_output") or gap_summary.get("recommended_route") or "gold_teacher"
    recommended_label = _recommended_route_label(recommended_route)
    listen_order = "先听 Gold Teacher，再听 Voice Matched，最后再听旧文本克隆。"
    return "\n".join(
        [
            "### 试听建议",
            f"- 推荐先听：{recommended_label}",
            f"- 试听顺序：{listen_order}",
            f"- 推荐策略：{voice_match_summary.get('recommendation_reason') or gap_summary.get('recommended_strategy') or '无'}",
            f"- 推荐原因：{gap_summary.get('recommended_reason') or '无'}",
            f"- Gold Teacher 输入层：{_input_mode_label(teacher_route.get('input_mode') or '')}",
            f"- Voice Matched 输入层：{_input_mode_label(voice_matched_route.get('input_mode') or '')}",
            f"- 旧文本克隆输入层：{_input_mode_label(legacy_clone_route.get('input_mode') or '')}",
        ]
    )


def build_text_compare_markdown(result: dict[str, Any]) -> str:
    asr = result.get("asr") or {}
    review = result.get("review") or {}
    rewrite = result.get("rewrite") or {}
    tts = result.get("tts") or {}
    teacher_route = _resolve_route(tts, "gold_teacher")
    voice_matched_route = _resolve_route(tts, "voice_matched")
    legacy_clone_route = _resolve_route(tts, "legacy_text_clone")
    rows = [
        ("原始 ASR", asr.get("punc_text") or asr.get("text") or "无"),
        ("审查后文本", review.get("asr_reviewed_text") or "无"),
        ("语义转写文本", rewrite.get("semantic_text") or rewrite.get("dialect_text") or "无"),
        ("发音转写文本", rewrite.get("pronunciation_text") or "无"),
        ("韵律润色文本", rewrite.get("prosody_text") or "无"),
        (
            f"Gold Teacher 输入文本（{_input_mode_label(teacher_route.get('input_mode') or '')}）",
            teacher_route.get("input_text") or "无",
        ),
        (
            f"Voice Matched 输入文本（{_input_mode_label(voice_matched_route.get('input_mode') or '')}）",
            voice_matched_route.get("input_text") or teacher_route.get("input_text") or "无",
        ),
        (
            f"旧文本克隆输入文本（{_input_mode_label(legacy_clone_route.get('input_mode') or '')}）",
            legacy_clone_route.get("input_text") or "无",
        ),
    ]
    lines = ["### 文本对比", "| 区域 | 内容 |", "| --- | --- |"]
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
            f"- Teacher vs 旧克隆内容差异：{gap_summary.get('content_diff') or '无'}",
            f"- Teacher vs 旧克隆发音差异：{gap_summary.get('pronunciation_diff') or '无'}",
            f"- Teacher vs 旧克隆流畅度差异：{gap_summary.get('fluency_diff') or '无'}",
            f"- 路由摘要：{gap_summary.get('route_summary') or '无'}",
            f"- 处理分工：{gap_summary.get('processing_split') or '无'}",
            f"- 归因标签：{gap_summary.get('issue_tag_summary') or '无'}",
            f"- Gold Teacher 优点：{gap_summary.get('baseline_advantage') or '无'}",
            f"- 旧文本克隆短板：{gap_summary.get('clone_weakness') or '无'}",
            f"- Voice Matched 可用：{'是' if voice_match_summary.get('voice_matched_available') else '否'}",
            f"- Voice Matched Provider：{voice_match_summary.get('voice_match_provider') or '无'}",
            f"- Voice Matched 错误：{voice_match_summary.get('voice_match_error') or '无'}",
            f"- 当前推荐：{recommended_label}",
        ]
    )


def build_route_cards_markdown(result: dict[str, Any]) -> tuple[str, str, str]:
    tts = result.get("tts") or {}
    teacher_route = _resolve_route(tts, "gold_teacher")
    voice_matched_route = _resolve_route(tts, "voice_matched")
    legacy_clone_route = _resolve_route(tts, "legacy_text_clone")
    recommended_route = tts.get("recommended_main_output") or "gold_teacher"

    def _build(route: dict[str, Any]) -> str:
        route_name = route.get("route_name") or "clone"
        is_recommended = route_name == recommended_route
        title = f"### {_route_label(route_name)}{'（推荐先听）' if is_recommended else ''}"
        return "\n".join(
            [
                title,
                f"- 输入层：{_input_mode_label(route.get('input_mode') or '')}",
                f"- 输入文本：{route.get('input_text') or '无'}",
                f"- 路由说明：{route.get('route_reason') or '无'}",
                f"- 模型/Provider：{route.get('tts_model') or route.get('voice_clone_provider') or '无'}",
                f"- 音色：{route.get('tts_voice') or route.get('voice_clone_provider') or '无'}",
                f"- 错误：{route.get('error') or '无'}",
            ]
        )

    return _build(teacher_route), _build(voice_matched_route), _build(legacy_clone_route)


def human_review_markdown(result: dict[str, Any]) -> str:
    asr = result.get("asr") or {}
    review = result.get("review") or {}
    rewrite = result.get("rewrite") or {}
    tts = result.get("tts") or {}
    teacher_route = _resolve_route(tts, "gold_teacher")
    voice_matched_route = _resolve_route(tts, "voice_matched")
    legacy_clone_route = _resolve_route(tts, "legacy_text_clone")
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
            f"- 审查后文本：{review.get('asr_reviewed_text') or '无'}",
            f"- Pivot 中文：{result.get('pivot_text_zh') or rewrite.get('pivot_text_zh') or '无'}",
            f"- 语义转写文本：{rewrite.get('semantic_text') or rewrite.get('dialect_text') or '无'}",
            f"- 发音转写文本：{rewrite.get('pronunciation_text') or '无'}",
            f"- 韵律润色文本：{rewrite.get('prosody_text') or '无'}",
            f"- 发音规则命中：{len(rewrite.get('pronunciation_rule_hits') or [])}",
            f"- 发音命中类别：{', '.join(rewrite.get('pronunciation_hit_categories') or []) or '无'}",
            f"- 发音回退：{'是' if rewrite.get('pronunciation_fallback_used') else '否'}",
            f"- 韵律回退：{'是' if rewrite.get('prosody_fallback_used') else '否'}",
            f"- 韵律命中类别：{', '.join(rewrite.get('prosody_hit_categories') or []) or '无'}",
            f"- 目标方言：{rewrite.get('target_dialect') or 'yue'}",
            f"- 方言风格：{rewrite.get('dialect_style') or 'guangdong_general'}",
            f"- 工作音频质量分：{work_audio.get('quality_score', '无')}",
            f"- 音色克隆：{'是' if tts.get('voice_clone_enabled') else '否'}",
            f"- 参考来源：{ref_source_label}",
            f"- 参考处理：{ref_audio.get('frontend_mode') or '无'}",
            f"- 参考拼接片段：{ref_frontend.get('speech_segment_count', 0)}",
            f"- 参考拼接时长：{ref_frontend.get('concat_duration_s', '无')}",
            f"- Gold Teacher 模型：{teacher_route.get('tts_model') or '无'}",
            f"- Gold Teacher 音色：{teacher_route.get('tts_voice') or '无'}",
            f"- Gold Teacher 输入模式：{_input_mode_label(teacher_route.get('input_mode') or '')}",
            f"- Gold Teacher 输入文本：{teacher_route.get('input_text') or '无'}",
            f"- Gold Teacher 路由说明：{teacher_route.get('route_reason') or '无'}",
            f"- Gold Teacher 音频文件：{Path(teacher_route.get('wav_path', '')).name if teacher_route.get('wav_path') else '无'}",
            f"- Gold Teacher 错误：{teacher_route.get('error') or '无'}",
            f"- Voice Matched Provider：{voice_matched_route.get('voice_clone_provider') or '无'}",
            f"- Voice Matched 输入模式：{_input_mode_label(voice_matched_route.get('input_mode') or '')}",
            f"- Voice Matched 路由说明：{voice_matched_route.get('route_reason') or '无'}",
            f"- Voice Matched 音频文件：{Path(voice_matched_route.get('wav_path', '')).name if voice_matched_route.get('wav_path') else '无'}",
            f"- Voice Matched 错误：{voice_matched_route.get('error') or '无'}",
            f"- 旧文本克隆来源：{legacy_clone_route.get('voice_clone_provider') or '系统音色'}",
            f"- 旧文本克隆音色优先级：{legacy_clone_route.get('speaker_similarity_priority') or 'high'}",
            f"- 旧文本克隆流畅度模式：{legacy_clone_route.get('tts_fluency_mode') or 'allow_rate_adjust'}",
            f"- 旧文本克隆输入模式：{_input_mode_label(legacy_clone_route.get('input_mode') or '')}",
            f"- 旧文本克隆输入文本：{legacy_clone_route.get('input_text') or '无'}",
            f"- 旧文本克隆路由说明：{legacy_clone_route.get('route_reason') or '无'}",
            f"- 旧文本克隆音频文件：{Path(legacy_clone_route.get('wav_path', '')).name if legacy_clone_route.get('wav_path') else '无'}",
            f"- 内容差异：{gap_summary.get('content_diff') or '无'}",
            f"- 发音差异：{gap_summary.get('pronunciation_diff') or '无'}",
            f"- 流畅度差异：{gap_summary.get('fluency_diff') or '无'}",
            f"- 路由摘要：{gap_summary.get('route_summary') or '无'}",
            f"- 处理分工：{gap_summary.get('processing_split') or '无'}",
            f"- 归因标签：{gap_summary.get('issue_tag_summary') or '无'}",
            f"- 推荐试听：{tts.get('recommended_main_output') or gap_summary.get('recommended_route') or 'gold_teacher'}",
            f"- 推荐策略：{voice_match_summary.get('recommendation_reason') or gap_summary.get('recommended_strategy') or '无'}",
            f"- 推荐原因：{gap_summary.get('recommended_reason') or '无'}",
            f"- Gold Teacher 优点：{gap_summary.get('baseline_advantage') or '无'}",
            f"- 旧文本克隆缺点：{gap_summary.get('clone_weakness') or '无'}",
        ]
    )
