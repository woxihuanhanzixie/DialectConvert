from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import gradio as gr

from .client import get_demo_capabilities, load_eval_rows, run_pipeline_from_audio
from .view_models import (
    build_cultural_cards_markdown,
    build_eval_table,
    build_gap_summary_markdown,
    build_recommendation_markdown,
    build_route_cards_markdown,
    build_text_compare_markdown,
    human_review_markdown,
    summarize_rows,
)

DIALECT_CHOICES = {
    "粤语": ("yue", "guangdong_general"),
    "四川话": ("sichuan", "sichuan_general"),
    "闽南语": ("minnan", "minnan_general"),
}


def _resolve_route(tts: dict[str, Any], route_name: str) -> dict[str, Any]:
    route = tts.get(route_name) or {}
    if route:
        return route
    if route_name == "qwen_cloned_dialect":
        route = tts.get("cloned_dialect") or tts.get("voice_matched") or tts.get("clone") or {}
        if route:
            return route
    if route_name in {"baseline", "gold_teacher"}:
        return {
            "route_name": "gold_teacher",
            "wav_path": tts.get("baseline_wav_path", ""),
            "audio_url": tts.get("baseline_audio_url", ""),
            "tts_model": tts.get("baseline_tts_model", ""),
            "tts_voice": tts.get("baseline_tts_voice", ""),
            "error": tts.get("baseline_error", ""),
            "input_text": tts.get("baseline_tts_input_text", ""),
            "input_mode": tts.get("baseline_tts_input_mode", ""),
            "audio_meta": tts.get("baseline_audio_meta"),
            "voice_clone_enabled": False,
            "route_reason": "",
            "teacher_input_text": tts.get("teacher_input_text", "") or tts.get("baseline_tts_input_text", ""),
            "teacher_input_mode": tts.get("teacher_input_mode", "") or tts.get("baseline_tts_input_mode", ""),
            "teacher_style_instruction": tts.get("teacher_style_instruction", "") or tts.get("tts_style_instructions", ""),
            "instruction_mode_active": tts.get("instruction_mode_active", False),
        }
    return {
        "route_name": "qwen_cloned_dialect",
        "wav_path": "",
        "audio_url": "",
        "tts_model": "",
        "tts_voice": "",
        "error": "",
        "input_text": "",
        "input_mode": "clean_dialect_text",
        "audio_meta": None,
        "voice_clone_enabled": False,
        "voice_clone_provider": "",
        "speaker_similarity_note": "",
        "clone_mode": "",
        "fallback_reason": "",
        "speaker_similarity_priority": "high",
        "tts_fluency_mode": "allow_rate_adjust",
        "route_reason": "",
        "teacher_input_text": tts.get("teacher_input_text", ""),
        "teacher_input_mode": "clean_dialect_text",
        "teacher_style_instruction": tts.get("teacher_style_instruction", "") or tts.get("tts_style_instructions", ""),
        "instruction_mode_active": tts.get("instruction_mode_active", False),
    }


def _prepare_preview_file(wav_path: str, trace_id: str, slot_name: str) -> str | None:
    if not wav_path:
        return None
    src = Path(wav_path)
    if not src.exists():
        return None
    preview_dir = Path("runtime_data") / "web_demo_preview" / (trace_id or "latest")
    preview_dir.mkdir(parents=True, exist_ok=True)
    dst = preview_dir / f"{slot_name}{src.suffix.lower() or '.wav'}"
    shutil.copy2(src, dst)
    return str(dst.resolve())


def _yes_no(value: bool) -> str:
    return "是" if value else "否"


def process_audio(
    audio_path: str,
    speaker_ref_audio: str,
    enable_punc: bool,
    enable_tts: bool,
    voice: str,
    target_dialect_label: str,
    segment_max_len: int,
    voice_clone_enabled: bool,
    voice_clone_provider: str,
):
    if not audio_path:
        raise gr.Error("请先上传音频或录音。")
    target_dialect, dialect_style = DIALECT_CHOICES.get(target_dialect_label, DIALECT_CHOICES["粤语"])
    result = run_pipeline_from_audio(
        audio_path,
        speaker_ref_audio=speaker_ref_audio or "",
        enable_punc=enable_punc,
        enable_rewrite=True,
        enable_tts=enable_tts,
        voice=voice,
        segment_max_len=segment_max_len,
        target_dialect=target_dialect,
        dialect_style=dialect_style,
        voice_clone_enabled=voice_clone_enabled,
        voice_clone_provider=voice_clone_provider,
    )
    asr = result.get("asr") or {}
    review = result.get("review") or {}
    rewrite = result.get("rewrite") or {}
    tts = result.get("tts") or {}
    source_audio = result.get("source_audio") or {}
    frontend = source_audio.get("audio_frontend") or {}
    raw_audio = frontend.get("raw_audio") or {}
    work_audio = frontend.get("work_audio") or {}
    clone_ref_audio = source_audio.get("voice_clone_ref_audio") or {}
    ref_frontend = clone_ref_audio.get("audio_frontend") or {}
    teacher_route = _resolve_route(tts, "gold_teacher")
    voice_matched_route = _resolve_route(tts, "qwen_cloned_dialect")
    gap_summary = tts.get("gap_summary") or {}
    voice_match_summary = tts.get("voice_match_summary") or {}

    teacher_input_text = (
        tts.get("teacher_input_text")
        or teacher_route.get("teacher_input_text")
        or teacher_route.get("input_text")
        or tts.get("tts_input_text")
        or ""
    )
    teacher_input_mode = (
        tts.get("teacher_input_mode")
        or teacher_route.get("teacher_input_mode")
        or teacher_route.get("input_mode")
        or tts.get("tts_input_mode")
        or ""
    )
    teacher_style_instruction = (
        tts.get("teacher_style_instruction")
        or teacher_route.get("teacher_style_instruction")
        or tts.get("tts_style_instructions")
        or ""
    )
    instruction_active = bool(tts.get("instruction_mode_active") or teacher_route.get("instruction_mode_active"))

    trace_id = str(result.get("trace_id") or "latest")
    teacher_audio = None
    teacher_download_audio = None
    if teacher_route.get("wav_path") and Path(teacher_route["wav_path"]).exists():
        teacher_audio = _prepare_preview_file(teacher_route["wav_path"], trace_id, "gold_teacher")
        teacher_download_audio = teacher_audio
    voice_matched_audio = None
    voice_matched_download_audio = None
    if voice_matched_route.get("wav_path") and Path(voice_matched_route["wav_path"]).exists():
        voice_matched_audio = _prepare_preview_file(voice_matched_route["wav_path"], trace_id, "qwen_cloned_dialect")
        voice_matched_download_audio = voice_matched_audio

    quality_box = "\n".join(
        [
            f"ASR Provider: {asr.get('asr_provider') or asr.get('provider') or 'unknown'}",
            f"ASR Model: {asr.get('asr_model') or asr.get('model') or 'unknown'}",
            f"ASR Request ID: {asr.get('request_id') or 'none'}",
            f"ASR fallback: {asr.get('cloud_asr_error') or 'none'}",
            f"原始时长: {raw_audio.get('duration_s', source_audio.get('duration_s', 0.0))}s",
            f"工作音频时长: {work_audio.get('duration_s', source_audio.get('duration_s', 0.0))}s",
            f"音频前端: {source_audio.get('frontend_mode') or 'none'}",
            f"质量分: {work_audio.get('quality_score', 'none')}",
            f"质量标记: {', '.join(work_audio.get('quality_flags') or []) or 'none'}",
            f"参考音频来源: {clone_ref_audio.get('source') or 'none'}",
            f"参考音频前端: {clone_ref_audio.get('frontend_mode') or 'none'}",
            f"参考音频时长: {clone_ref_audio.get('duration_s', 0.0)}s",
        ]
    )
    clone_box = "\n".join(
        [
            f"Qwen Voice Copy 启用: {'是' if voice_matched_route.get('voice_clone_enabled') else '否'}",
            f"Provider: {voice_match_summary.get('voice_match_provider') or voice_matched_route.get('voice_clone_provider') or 'qwen_standard_tts'}",
            f"输入模式: {voice_matched_route.get('input_mode') or 'clean_dialect_text'}",
            f"Source: cleaned dialect text ({voice_matched_route.get('input_mode') or 'none'})",
            f"Target: reference audio ({Path(clone_ref_audio.get('path', '')).name if clone_ref_audio.get('path') else 'none'})",
            f"回退原因: {voice_matched_route.get('fallback_reason') or voice_match_summary.get('voice_match_error') or 'none'}",
            f"说明: {voice_matched_route.get('speaker_similarity_note') or 'none'}",
        ]
    )
    latencies = "\n".join(
        [
            f"ASR: {asr.get('latency_ms', 0)} ms",
            f"Review: {(review or {}).get('llm_latency_ms', 0)} ms",
            f"Rewrite: {(rewrite or {}).get('llm_latency_ms', 0)} ms",
            "Gold Teacher: hidden",
            f"Qwen Voice Copy: {voice_matched_route.get('latency_ms', 0)} ms",
            f"TTS Total: {(tts or {}).get('latency_ms', 0)} ms",
            f"Total: {result.get('total_latency_ms', 0)} ms",
        ]
    )
    pron_box = "\n".join(
        [
            f"发音模式: {rewrite.get('pronunciation_mode') or 'rule_first'}",
            f"发音规则命中: {len(rewrite.get('pronunciation_rule_hits') or [])}",
            f"发音命中类别: {', '.join(rewrite.get('pronunciation_hit_categories') or []) or 'none'}",
            f"韵律模式: {rewrite.get('prosody_mode') or 'rule_plus_llm'}",
            f"韵律规则命中: {len(rewrite.get('prosody_rule_hits') or [])}",
            f"韵律命中类别: {', '.join(rewrite.get('prosody_hit_categories') or []) or 'none'}",
        ]
    )
    teacher_instruction_status = "\n".join(
        [
            f"Teacher input mode: {teacher_input_mode or 'unknown'}",
            f"Instruction parameter active: {_yes_no(instruction_active)}",
        ]
    )

    recommendation_md = build_recommendation_markdown(result)
    text_compare_md = build_text_compare_markdown(result)
    gap_summary_md = build_gap_summary_markdown(result)
    teacher_card_md, voice_matched_card_md = build_route_cards_markdown(result)
    cultural_cards_md = build_cultural_cards_markdown(result)
    error_text = (voice_matched_route.get("error") or "") + (
        f"\nGold Teacher 错误: {teacher_route.get('error')}" if teacher_route.get("error") else ""
    )

    return (
        teacher_input_text,
        teacher_style_instruction,
        teacher_instruction_status,
        asr.get("punc_text") or asr.get("text") or "",
        review.get("asr_reviewed_text") or "",
        rewrite.get("tn_text") or "",
        result.get("pivot_text_zh") or rewrite.get("pivot_text_zh") or "",
        rewrite.get("prosody_text") or rewrite.get("pronunciation_text") or rewrite.get("dialect_text") or rewrite.get("semantic_text") or "",
        cultural_cards_md,
        rewrite.get("pronunciation_text") or "",
        rewrite.get("prosody_text") or "",
        quality_box,
        pron_box,
        clone_box,
        latencies,
        error_text,
        recommendation_md,
        teacher_audio,
        teacher_download_audio,
        voice_matched_audio,
        voice_matched_download_audio,
        text_compare_md,
        gap_summary_md,
        teacher_card_md,
        voice_matched_card_md,
        human_review_markdown(result),
        json.dumps(result, ensure_ascii=False, indent=2),
    )


def run_eval():
    rows = load_eval_rows()
    stats = summarize_rows(rows)
    stats_md = "\n".join(
        [
            "### 现有样本评估",
            f"- 样本数：{stats['total']}",
            f"- TTS 成功：{stats['tts_ok']}",
            f"- TTS 失败：{stats['tts_failed']}",
            f"- 平均改写耗时：{stats['avg_rewrite_latency_ms']} ms",
            f"- 平均 TTS 耗时：{stats['avg_tts_latency_ms']} ms",
        ]
    )
    return stats_md, build_eval_table(rows)


def build_demo() -> gr.Blocks:
    caps = get_demo_capabilities()
    provider_choices = ["qwen_voice_clone"]
    default_provider = str(caps.get("voice_conversion_provider") or "qwen_voice_clone").strip().lower()
    if default_provider not in provider_choices:
        provider_choices.insert(0, default_provider)

    with gr.Blocks(title="Demo1 多方言语音网页演示") as demo:
        gr.Markdown("# Demo1 多方言语音网页演示")
        gr.Markdown(
            f"当前支持上传格式：`{', '.join(caps['supported_upload_exts'])}`  \n"
            f"FFmpeg 可用：`{caps['ffmpeg_available']}`  \n"
            f"ASR 默认链路：`{caps.get('asr_provider', 'api_first')}` / `{caps.get('asr_cloud_model', '')}`；"
            f"API Key：`{caps.get('asr_cloud_api_key_configured', False)}`  \n"
            f"Qwen Voice Copy Provider：`{default_provider}`；模式：`qwen_voice_clone_api`  \n"
            f"参考音频策略：`{caps.get('reference_audio_strategy', 'vad_concat')}`；建议时长："
            f"`{caps.get('speaker_ref_audio_min_s', 10)}-{caps.get('speaker_ref_audio_max_s', 20)}s`  \n"
            f"{caps['microphone_hint']}"
        )
        with gr.Tabs():
            with gr.Tab("完整演示页"):
                with gr.Row(equal_height=False):
                    with gr.Column(scale=1, min_width=380):
                        input_audio = gr.Audio(sources=["upload", "microphone"], type="filepath", label="上传或直接录音")
                        speaker_ref_audio = gr.Audio(
                            sources=["upload", "microphone"],
                            type="filepath",
                            label="音色参考音频（用于 Qwen Voice Copy，可选）",
                        )
                        with gr.Group():
                            gr.Markdown("### Qwen Voice Copy")
                            voice_clone_enabled = gr.Checkbox(value=True, label="启用 Qwen 声音复刻")
                            voice_clone_provider = gr.Dropdown(
                                choices=provider_choices,
                                value=default_provider,
                                label="Voice Copy Provider",
                            )
                            gr.Markdown(
                                "公网主链路直接使用 Qwen voice enrollment + qwen3-tts-vc 合成最终方言克隆音频。"
                                "没有参考音频时会明确回退到普通 Qwen TTS。"
                            )
                        with gr.Group():
                            gr.Markdown("### 文本与 TTS")
                            enable_punc = gr.Checkbox(value=True, label="启用标点增强")
                            enable_tts = gr.Checkbox(value=True, label="启用 Qwen Voice Copy / TTS")
                            voice = gr.Dropdown(choices=["Kiki", "Rocky"], value="Kiki", label="普通 TTS 兜底音色")
                            target_dialect = gr.Dropdown(choices=list(DIALECT_CHOICES), value="粤语", label="目标方言")
                            segment_max_len = gr.Slider(16, 48, value=28, step=1, label="分段长度")
                        run_btn = gr.Button("开始转换", variant="primary")
                    with gr.Column(scale=2, min_width=640):
                        recommendation_md = gr.Markdown(label="试听建议")
                        with gr.Row():
                            with gr.Column():
                                teacher_audio = gr.Audio(label="Gold Teacher 内部兜底音频", visible=False)
                                teacher_download_audio = gr.File(label="下载 Gold Teacher 音频", visible=False)
                                teacher_card_md = gr.Markdown(visible=False)
                            with gr.Column():
                                voice_matched_audio = gr.Audio(label="最终方言克隆音频")
                                voice_matched_download_audio = gr.File(label="下载最终方言克隆音频")
                                voice_matched_card_md = gr.Markdown()
                        text_compare_md = gr.Markdown()
                        teacher_input_text = gr.Textbox(label="Qwen TTS teacher 输入文本", lines=4)
                        teacher_style_instruction = gr.Textbox(label="方言 style instruction", lines=4)
                        teacher_instruction_status = gr.Textbox(label="Teacher 控制状态", lines=2)
                        gap_summary_md = gr.Markdown()

                with gr.Row(equal_height=False):
                    with gr.Column(scale=1):
                        asr_text = gr.Textbox(label="ASR 原始文本", lines=3)
                        reviewed_text = gr.Textbox(label="审查后语义普通话", lines=3)
                        tn_text = gr.Textbox(label="Rewrite 前文本", lines=3)
                        pivot_text = gr.Textbox(label="Pivot 中文", lines=3)
                        yue_text = gr.Textbox(label="方言发声文本（用于 Qwen 克隆合成前的清洗候选）", lines=4)
                        cultural_cards_md = gr.Markdown()
                        pronunciation_text = gr.Textbox(label="发音转写文本", lines=4)
                        prosody_text = gr.Textbox(label="韵律润色文本", lines=4)
                        quality_box = gr.Textbox(label="输入质量与语音识别", lines=6)
                        pron_box = gr.Textbox(label="发音/韵律修正状态", lines=6)
                        clone_box = gr.Textbox(label="音色迁移状态", lines=7)
                        latency_box = gr.Textbox(label="耗时统计", lines=7)
                        error_box = gr.Textbox(label="错误/降级提示", lines=4)
                    with gr.Column(scale=1):
                        review_md = gr.Markdown()
                        json_panel = gr.Code(label="结构化结果", language="json")

                run_btn.click(
                    process_audio,
                    inputs=[
                        input_audio,
                        speaker_ref_audio,
                        enable_punc,
                        enable_tts,
                        voice,
                        target_dialect,
                        segment_max_len,
                        voice_clone_enabled,
                        voice_clone_provider,
                    ],
                    outputs=[
                        teacher_input_text,
                        teacher_style_instruction,
                        teacher_instruction_status,
                        asr_text,
                        reviewed_text,
                        tn_text,
                        pivot_text,
                        yue_text,
                        cultural_cards_md,
                        pronunciation_text,
                        prosody_text,
                        quality_box,
                        pron_box,
                        clone_box,
                        latency_box,
                        error_box,
                        recommendation_md,
                        teacher_audio,
                        teacher_download_audio,
                        voice_matched_audio,
                        voice_matched_download_audio,
                        text_compare_md,
                        gap_summary_md,
                        teacher_card_md,
                        voice_matched_card_md,
                        review_md,
                        json_panel,
                    ],
                )

            with gr.Tab("结果评估页"):
                eval_btn = gr.Button("刷新评估")
                stats_md = gr.Markdown()
                table = gr.Dataframe(headers=["uttid", "source_text", "dialect_text", "tts_status", "tts_wav_path"])
                eval_btn.click(run_eval, outputs=[stats_md, table])

    return demo


def main() -> None:
    demo = build_demo()
    demo.launch(server_name="127.0.0.1", server_port=7860)


if __name__ == "__main__":
    main()
