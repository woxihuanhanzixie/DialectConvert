from __future__ import annotations

import json
import shutil
from pathlib import Path

import gradio as gr

from .client import get_demo_capabilities, load_eval_rows, run_pipeline_from_audio
from .view_models import (
    build_eval_table,
    build_gap_summary_markdown,
    build_recommendation_markdown,
    build_route_cards_markdown,
    build_text_compare_markdown,
    human_review_markdown,
    summarize_rows,
)


def _resolve_route(tts: dict, route_name: str) -> dict:
    route = tts.get(route_name) or {}
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
        }
    if route_name == "voice_matched":
        return {
            "route_name": "voice_matched",
            "wav_path": "",
            "audio_url": "",
            "tts_model": "",
            "tts_voice": "",
            "error": "",
            "input_text": "",
            "input_mode": "teacher_audio_to_audio",
            "audio_meta": None,
            "voice_clone_enabled": False,
            "voice_clone_provider": "",
            "speaker_similarity_note": "",
            "clone_mode": "",
            "fallback_reason": "",
            "speaker_similarity_priority": "high",
            "tts_fluency_mode": "allow_rate_adjust",
            "route_reason": "",
        }
    return {"route_name": route_name}


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


def process_audio(
    audio_path: str,
    speaker_ref_audio: str,
    enable_punc: bool,
    enable_tts: bool,
    voice: str,
    segment_max_len: int,
    voice_clone_enabled: bool,
    voice_clone_provider: str,
):
    if not audio_path:
        raise gr.Error("请先上传音频或录音。")
    result = run_pipeline_from_audio(
        audio_path,
        speaker_ref_audio=speaker_ref_audio or "",
        enable_punc=enable_punc,
        enable_rewrite=True,
        enable_tts=enable_tts,
        voice=voice,
        segment_max_len=segment_max_len,
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
    voice_matched_route = _resolve_route(tts, "voice_matched")
    gap_summary = tts.get("gap_summary") or {}
    voice_match_summary = tts.get("voice_match_summary") or {}
    clone_ref_source = clone_ref_audio.get("source", "")
    if clone_ref_source == "input_audio_auto":
        clone_ref_label = "主音频自动复用"
    elif clone_ref_source == "uploaded_ref":
        clone_ref_label = "单独上传参考音频"
    else:
        clone_ref_label = "无"
    json_panel = json.dumps(result, ensure_ascii=False, indent=2)
    teacher_audio = None
    teacher_download_audio = None
    voice_matched_audio = None
    voice_matched_download_audio = None
    if teacher_route.get("wav_path") and Path(teacher_route["wav_path"]).exists():
        teacher_preview = _prepare_preview_file(
            teacher_route["wav_path"],
            result.get("trace_id", ""),
            "gold_teacher",
        )
        teacher_audio = teacher_preview
        teacher_download_audio = teacher_preview
    if voice_matched_route.get("wav_path") and Path(voice_matched_route["wav_path"]).exists():
        vm_preview = _prepare_preview_file(
            voice_matched_route["wav_path"],
            result.get("trace_id", ""),
            "voice_matched",
        )
        voice_matched_audio = vm_preview
        voice_matched_download_audio = vm_preview
    latencies = "\n".join(
        [
            f"ASR: {asr.get('latency_ms', 0)} ms",
            f"Review: {review.get('review_latency_ms', 0)} ms",
            f"Rewrite: {rewrite.get('llm_latency_ms', 0)} ms",
            f"Gold Teacher: {(tts.get('gold_teacher') or {}).get('latency_ms', 0)} ms",
            f"Voice Matched: {(tts.get('voice_matched') or {}).get('latency_ms', 0)} ms",
            f"TTS Total: {tts.get('latency_ms', 0)} ms",
            f"Total: {result.get('total_latency_ms', 0)} ms",
        ]
    )
    quality_box = "\n".join(
        [
            f"输入语言: {result.get('input_lang', '未知')}",
            f"目标方言: {rewrite.get('target_dialect') or 'yue'}",
            f"方言风格: {rewrite.get('dialect_style') or 'guangdong_general'}",
            f"Raw 质量分: {raw_audio.get('quality_score', '无')}",
            f"Work 质量分: {work_audio.get('quality_score', '无')}",
            f"风险标记: {', '.join(work_audio.get('quality_flags', [])) or '无'}",
        ]
    )
    clone_box = "\n".join(
        [
            f"音色转换启用: {'是' if voice_matched_route.get('voice_clone_enabled') else '否'}",
            f"参考来源: {clone_ref_label}",
            f"参考处理: {clone_ref_audio.get('frontend_mode') or '无'}",
            f"拼接片段数: {ref_frontend.get('speech_segment_count', 0)}",
            f"拼接后时长: {ref_frontend.get('concat_duration_s', '无')}",
            f"Voice Matched Provider: {voice_match_summary.get('voice_match_provider') or voice_matched_route.get('voice_clone_provider') or '无'}",
            f"音色优先级: {voice_matched_route.get('speaker_similarity_priority') or 'high'}",
            f"流畅度模式: {voice_matched_route.get('tts_fluency_mode') or 'allow_rate_adjust'}",
            f"Gold Teacher 输入模式: {teacher_route.get('input_mode') or '未知'}",
            f"Voice Matched 输入模式: {voice_matched_route.get('input_mode') or '未知'}",
            f"推荐主输出: {tts.get('recommended_main_output') or 'gold_teacher'}",
            f"推荐策略: {voice_match_summary.get('recommendation_reason') or gap_summary.get('recommended_strategy') or '无'}",
            f"Voice Matched 说明: {voice_matched_route.get('speaker_similarity_note') or '无'}",
            f"Voice Matched 回退: {voice_matched_route.get('fallback_reason') or voice_match_summary.get('voice_match_error') or '无'}",
        ]
    )
    pron_box = "\n".join(
        [
            f"发音模式: {rewrite.get('pronunciation_mode') or 'rule_first'}",
            f"规则命中数: {len(rewrite.get('pronunciation_rule_hits') or [])}",
            f"发音命中类别: {', '.join(rewrite.get('pronunciation_hit_categories') or []) or '无'}",
            f"是否触发 LLM 回退: {'是' if rewrite.get('pronunciation_fallback_used') else '否'}",
            f"发音说明: {rewrite.get('pronunciation_notes') or '无'}",
            f"韵律模式: {rewrite.get('prosody_mode') or 'rule_plus_llm'}",
            f"韵律规则命中: {len(rewrite.get('prosody_rule_hits') or [])}",
            f"韵律命中类别: {', '.join(rewrite.get('prosody_hit_categories') or []) or '无'}",
            f"韵律回退: {'是' if rewrite.get('prosody_fallback_used') else '否'}",
        ]
    )
    recommendation_md = build_recommendation_markdown(result)
    text_compare_md = build_text_compare_markdown(result)
    gap_summary_md = build_gap_summary_markdown(result)
    teacher_card_md, voice_matched_card_md = build_route_cards_markdown(result)
    return (
        asr.get("punc_text") or asr.get("text") or "",
        review.get("asr_reviewed_text") or "",
        rewrite.get("tn_text") or "",
        result.get("pivot_text_zh") or rewrite.get("pivot_text_zh") or "",
        rewrite.get("semantic_text") or rewrite.get("dialect_text") or "",
        rewrite.get("pronunciation_text") or "",
        rewrite.get("prosody_text") or "",
        quality_box,
        pron_box,
        clone_box,
        latencies,
        (voice_matched_route.get("error") or "")
        + (f"\nGold Teacher 错误: {teacher_route.get('error')}" if teacher_route.get("error") else "")
        ,
        teacher_audio,
        teacher_download_audio,
        voice_matched_audio,
        voice_matched_download_audio,
        recommendation_md,
        teacher_card_md,
        voice_matched_card_md,
        text_compare_md,
        gap_summary_md,
        human_review_markdown(result),
        json_panel,
    )


def load_eval_panel():
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
    with gr.Blocks(title="Demo1 粤语语音演示") as demo:
        gr.Markdown("# Demo1 粤语语音网页演示")
        gr.Markdown(
            f"当前支持上传格式：`{', '.join(caps['supported_upload_exts'])}`  \n"
            f"FFmpeg 可用：`{caps['ffmpeg_available']}`  \n"
            f"{caps['microphone_hint']}"
        )
        with gr.Tabs():
            with gr.Tab("完整演示页"):
                with gr.Row():
                    with gr.Column(scale=1):
                        input_audio = gr.Audio(
                            sources=["upload", "microphone"],
                            type="filepath",
                            label="上传或直接录音",
                        )
                        speaker_ref_audio = gr.Audio(
                            sources=["upload", "microphone"],
                            type="filepath",
                            label="音色参考音频（用于 Voice Matched，可选）",
                        )
                        gr.Markdown("高级预留：后续会增加 `Prosody Ref` 双参考模式，首版默认不启用。")
                        enable_punc = gr.Checkbox(value=True, label="启用标点增强")
                        enable_tts = gr.Checkbox(value=True, label="启用 TTS")
                        voice_clone_enabled = gr.Checkbox(value=False, label="启用 Voice Matched")
                        voice_clone_provider = gr.Dropdown(
                            choices=["none", "rvc", "openvoice", "gpt_sovits", "fish_speech", "qwen_vc"],
                            value="openvoice",
                            label="音色转换 Provider",
                        )
                        voice = gr.Dropdown(choices=["Kiki", "Rocky"], value="Kiki", label="粤语音色")
                        segment_max_len = gr.Slider(16, 48, value=28, step=1, label="分段长度")
                        run_btn = gr.Button("开始转换", variant="primary")
                    with gr.Column(scale=1):
                        recommendation_md = gr.Markdown(label="试听建议")
                        with gr.Row():
                            with gr.Column():
                                teacher_audio = gr.Audio(label="Gold Teacher 音频")
                                teacher_download_audio = gr.File(label="下载 Gold Teacher 音频")
                                teacher_card_md = gr.Markdown()
                            with gr.Column():
                                voice_matched_audio = gr.Audio(label="Voice Matched 音频")
                                voice_matched_download_audio = gr.File(label="下载 Voice Matched 音频")
                                voice_matched_card_md = gr.Markdown()
                        text_compare_md = gr.Markdown()
                        gap_summary_md = gr.Markdown()
                    with gr.Column(scale=1):
                        asr_text = gr.Textbox(label="ASR 原始文本", lines=3)
                        reviewed_text = gr.Textbox(label="审查后文本", lines=3)
                        tn_text = gr.Textbox(label="Rewrite 前文本", lines=3)
                        pivot_text = gr.Textbox(label="Pivot 中文", lines=3)
                        yue_text = gr.Textbox(label="语义转写文本", lines=4)
                        pronunciation_text = gr.Textbox(label="发音转写文本", lines=4)
                        prosody_text = gr.Textbox(label="韵律润色文本", lines=4)
                        quality_box = gr.Textbox(label="输入质量与语言", lines=4)
                        pron_box = gr.Textbox(label="发音/韵律修正状态", lines=6)
                        clone_box = gr.Textbox(label="音色克隆状态", lines=5)
                        latency_box = gr.Textbox(label="耗时统计", lines=5)
                        error_box = gr.Textbox(label="错误/降级提示", lines=4)
                    with gr.Column(scale=1):
                        review_md = gr.Markdown()
                        json_panel = gr.Code(label="结构化结果", language="json")

                run_btn.click(
                    process_audio,
                    inputs=[input_audio, speaker_ref_audio, enable_punc, enable_tts, voice, segment_max_len, voice_clone_enabled, voice_clone_provider],
                    outputs=[
                        asr_text,
                        reviewed_text,
                        tn_text,
                        pivot_text,
                        yue_text,
                        pronunciation_text,
                        prosody_text,
                        quality_box,
                        pron_box,
                        clone_box,
                        latency_box,
                        error_box,
                        teacher_audio,
                        teacher_download_audio,
                        voice_matched_audio,
                        voice_matched_download_audio,
                        recommendation_md,
                        teacher_card_md,
                        voice_matched_card_md,
                        text_compare_md,
                        gap_summary_md,
                        review_md,
                        json_panel,
                    ],
                )
            with gr.Tab("结果评估页"):
                stats_md = gr.Markdown()
                eval_table = gr.Dataframe(
                    headers=["uttid", "source_text", "yue_text", "tts_status", "tts_wav_path"],
                    interactive=False,
                    wrap=True,
                )
                refresh_btn = gr.Button("刷新评估结果")
                refresh_btn.click(load_eval_panel, outputs=[stats_md, eval_table])
                demo.load(load_eval_panel, outputs=[stats_md, eval_table])
    return demo


if __name__ == "__main__":
    build_demo().launch(server_name="127.0.0.1", server_port=7860)
