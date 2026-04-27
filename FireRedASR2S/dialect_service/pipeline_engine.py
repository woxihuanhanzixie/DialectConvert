from __future__ import annotations

import uuid
from pathlib import Path
from time import perf_counter
from typing import Any

import soundfile as sf

from asr_service.asr_engine import get_asr_engine
from asr_service.system_engine import get_asr_system_engine
from fireredasr2s.dialect_pipeline.config import Step2Config

from .adapters import (
    review_asr_text,
    review_asr_text_en,
    rewrite_text,
    translate_en_to_pivot_zh,
    tts_gold_teacher,
    tts_text,
    tts_voice_match_from_teacher,
)


class DialectPipelineEngine:
    def __init__(self) -> None:
        self.cfg = Step2Config.from_env()

    def health(self) -> dict[str, Any]:
        return {
            "provider": self.cfg.provider,
            "qwen_tts_model": self.cfg.qwen_tts_model,
            "qwen_tts_voice": self.cfg.qwen_tts_voice,
            "output_dir": str(self.cfg.output_dir),
        }

    def _resolve_clone_route_input(self, rewrite: dict[str, Any] | None, fallback_text: str) -> tuple[str, str, str]:
        if not rewrite:
            return (
                fallback_text,
                "review_text",
                "未生成改写层时，克隆链路回退到审查文本，优先保证可生成。",
            )
        target_text = (
            rewrite.get("prosody_text")
            or rewrite.get("pronunciation_text")
            or rewrite.get("semantic_text")
            or rewrite.get("dialect_text")
            or fallback_text
        )
        input_mode = (
            "prosody_text"
            if rewrite.get("prosody_text")
            else (
                "pronunciation_text"
                if rewrite.get("pronunciation_text")
                else ("semantic_text" if rewrite.get("semantic_text") else "dialect_text")
            )
        )
        reason_map = {
            "prosody_text": "克隆链路默认消费韵律层，集中承接连接词、停顿和口语衔接调整，同时验证声纹承载能力。",
            "pronunciation_text": "克隆链路退回发音层，优先验证专名和口语读法修正，不额外叠加韵律风险。",
            "semantic_text": "克隆链路退回语义层，当前仅验证改写文本与声纹承载，不做细粒度发音/韵律控制。",
            "dialect_text": "克隆链路仅拿到基础方言文本，作为最小可用输入继续生成。",
        }
        return target_text, input_mode, reason_map.get(input_mode, "克隆链路使用默认输入文本。")

    def _resolve_baseline_route_input(self, rewrite: dict[str, Any] | None, fallback_text: str) -> tuple[str, str, str]:
        if not rewrite:
            return (
                fallback_text,
                "review_text",
                "未生成改写层时，基线链路回退到审查文本，作为内容与自然度兜底参考。",
            )
        if rewrite.get("semantic_text"):
            return (
                rewrite["semantic_text"],
                "semantic_text",
                "基线链路默认消费语义层，只保留内容改写结果，不主动引入额外发音和韵律干预。",
            )
        if rewrite.get("dialect_text"):
            return (
                rewrite["dialect_text"],
                "dialect_text",
                "基线链路退回基础方言文本，继续承担系统自然度和内容正确性参考。",
            )
        return (
            fallback_text,
            "review_text",
            "未拿到方言改写文本时，基线链路直接消费审查文本作为兜底。",
        )

    def _build_route_payload(
        self,
        route_name: str,
        tts_result: dict[str, Any],
        *,
        input_text: str,
        input_mode: str,
        route_reason: str,
        default_voice: str,
        voice_clone_enabled: bool,
    ) -> dict[str, Any]:
        return {
            "route_name": route_name,
            "wav_path": tts_result.get("wav_path", ""),
            "audio_url": tts_result.get("audio_url", ""),
            "expires_at": tts_result.get("expires_at", ""),
            "tts_model": self.cfg.qwen_tts_model,
            "tts_voice": tts_result.get("voice") or default_voice,
            "latency_ms": tts_result.get("latency_ms", 0.0),
            "error": tts_result.get("error", ""),
            "input_text": input_text,
            "input_mode": input_mode,
            "route_role": "stability_reference" if route_name == "baseline" else "control_experiment",
            "route_reason": route_reason,
            "audio_meta": self._audio_meta(tts_result.get("wav_path", "")),
            "voice_clone_enabled": voice_clone_enabled,
            "voice_clone_provider": tts_result.get("voice_clone_provider", ""),
            "speaker_similarity_note": tts_result.get("speaker_similarity_note", ""),
            "clone_mode": tts_result.get("clone_mode", ""),
            "fallback_reason": tts_result.get("fallback_reason", ""),
            "speaker_similarity_priority": tts_result.get("speaker_similarity_priority", self.cfg.speaker_similarity_priority),
            "tts_fluency_mode": tts_result.get("tts_fluency_mode", self.cfg.tts_fluency_mode),
            "tts_style_instructions": tts_result.get("tts_style_instructions", self.cfg.tts_style_instructions),
            "instruction_mode_active": tts_result.get("instruction_mode_active", False),
        }

    def _build_gap_summary(
        self,
        *,
        baseline_route: dict[str, Any],
        clone_route: dict[str, Any],
        rewrite: dict[str, Any] | None,
        voice_clone_enabled: bool,
    ) -> dict[str, Any]:
        baseline_mode = baseline_route.get("input_mode") or "review_text"
        clone_mode = clone_route.get("input_mode") or "review_text"
        baseline_text = baseline_route.get("input_text") or ""
        clone_text = clone_route.get("input_text") or ""
        clone_error = clone_route.get("error") or ""
        baseline_error = baseline_route.get("error") or ""
        pronunciation_hits = rewrite.get("pronunciation_rule_hits") if rewrite else []
        prosody_hits = rewrite.get("prosody_rule_hits") if rewrite else []
        pronunciation_categories = rewrite.get("pronunciation_hit_categories") if rewrite else []
        prosody_categories = rewrite.get("prosody_hit_categories") if rewrite else []

        if baseline_text == clone_text:
            content_diff = "两路输入文本一致，当前内容层没有额外分叉，重点应放在听感对比。"
        else:
            content_diff = (
                f"基线链路使用 {baseline_mode}，对比链路使用 {clone_mode}，"
                "两路输入文本已经分层，便于区分自然度与声纹承载效果。"
            )

        if clone_mode == "prosody_text":
            pronunciation_diff = "对比链路使用韵律润色文本，通常会保留更多停顿和口语连读写法，发音控制更激进。"
        elif clone_mode == "pronunciation_text":
            pronunciation_diff = "对比链路使用发音转写文本，更强调专名和口语读法；基线链路保留系统自然发音。"
        else:
            pronunciation_diff = "两路都未显式切到独立发音层，发音差异主要来自模型本身而不是输入文本。"

        if clone_error:
            fluency_diff = "对比链路当前生成异常，流畅度无法稳定评估，应优先以基线结果试听。"
        elif voice_clone_enabled and clone_mode == "prosody_text":
            fluency_diff = "对比链路同时承担声纹克隆和韵律写法，句间衔接更容易变硬，基线通常更稳。"
        elif voice_clone_enabled:
            fluency_diff = "对比链路承担声纹承载任务，整体流畅度风险通常高于不带克隆负担的基线链路。"
        elif clone_mode != baseline_mode:
            fluency_diff = "当前是双文本双策略对比，基线更偏系统自然度，对比链路更偏发音或韵律控制。"
        else:
            fluency_diff = "两路流畅度策略接近，建议以实际听感为准做后续调参。"

        route_summary = (
            f"基线链路固定承担稳定参考，默认输入为 {baseline_mode}；"
            f"克隆链路承担控制增强与声纹验证，默认输入为 {clone_mode}。"
        )
        processing_split = self._build_processing_split(pronunciation_categories, prosody_categories, clone_mode)
        issue_tags = self._build_issue_tags(
            baseline_mode=baseline_mode,
            clone_mode=clone_mode,
            baseline_error=baseline_error,
            clone_error=clone_error,
            voice_clone_enabled=voice_clone_enabled,
            pronunciation_hits=pronunciation_hits or [],
            prosody_hits=prosody_hits or [],
        )
        issue_tag_summary = self._summarize_issue_tags(issue_tags)

        recommended_route = "baseline"
        recommended_strategy = "先听基线，再决定是否保留克隆链路增强。"
        recommended_reason = "基线链路更适合作为首听参考，便于先确认内容与自然度是否稳定。"
        if baseline_error and not clone_error:
            recommended_route = "clone"
            recommended_strategy = "基线异常，直接以克隆链路作为本轮主结果。"
            recommended_reason = "基线链路当前生成异常，对比链路可作为本轮试听主结果。"
        elif clone_error and not baseline_error:
            recommended_route = "baseline"
            recommended_strategy = "克隆异常，回到基线链路完成试听与验收。"
            recommended_reason = "对比链路生成异常，当前应优先试听基线链路。"
        elif voice_clone_enabled and clone_mode == "prosody_text":
            recommended_route = "baseline"
            recommended_strategy = "先用基线确认自然度，再用克隆核对专名和声纹收益。"
            recommended_reason = "克隆链路同时承担声纹与韵律控制，适合做增益对比，不宜直接取代基线首听。"
        elif voice_clone_enabled and clone_mode == "pronunciation_text":
            recommended_route = "clone"
            recommended_strategy = "先听克隆确认专名读法，再回听基线判断自然度是否被破坏。"
            recommended_reason = "当前克隆链路聚焦发音层，能更直接验证专名和口语读法修正收益。"
        elif not voice_clone_enabled and clone_mode in {"prosody_text", "pronunciation_text"}:
            recommended_route = "clone"
            recommended_strategy = "无声纹负担时优先试听克隆链路，直接验证文本控制收益。"
            recommended_reason = "当前未启用声纹克隆，对比链路能更直接验证发音或韵律文本带来的收益。"

        baseline_advantage = "基线链路更接近系统默认自然度，适合作为内容正确性和句间衔接的参考。"
        clone_weakness = (
            "对比链路更容易受到专名纠音、停顿写法或声纹承载负担影响，需要和基线对听判断是否值得保留。"
        )
        if recommended_route == "clone":
            baseline_advantage = "基线链路可继续作为稳定兜底，用于判断对比链路是否出现明显劣化。"
            clone_weakness = "当前对比链路已经带来更强的发音或韵律控制，但仍需关注是否引入生硬停顿。"

        return {
            "content_diff": content_diff,
            "pronunciation_diff": pronunciation_diff,
            "fluency_diff": fluency_diff,
            "route_summary": route_summary,
            "processing_split": processing_split,
            "issue_tags": issue_tags,
            "issue_tag_summary": issue_tag_summary,
            "recommended_route": recommended_route,
            "recommended_strategy": recommended_strategy,
            "recommended_reason": recommended_reason,
            "baseline_advantage": baseline_advantage,
            "clone_weakness": clone_weakness,
        }

    def _build_processing_split(
        self,
        pronunciation_categories: list[str],
        prosody_categories: list[str],
        clone_mode: str,
    ) -> str:
        pronunciation_side = "专名词优先放在发音层处理"
        if "connector" in pronunciation_categories or "function_word" in pronunciation_categories:
            pronunciation_side += "，并补充少量高风险口语词纠音"
        prosody_side = "连接词、句间衔接和轻停顿优先放在韵律层处理"
        if clone_mode != "prosody_text":
            prosody_side += "；当前克隆链路未直接消费韵律层，相关收益需要后续样本再验证"
        if "named_entity" in prosody_categories:
            prosody_side += "；韵律层会保护已修好的专名词面，避免被改回普通话写法"
        return f"{pronunciation_side}。{prosody_side}。"

    def _build_issue_tags(
        self,
        *,
        baseline_mode: str,
        clone_mode: str,
        baseline_error: str,
        clone_error: str,
        voice_clone_enabled: bool,
        pronunciation_hits: list[dict[str, Any]],
        prosody_hits: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        tags: list[dict[str, Any]] = []
        if baseline_mode != clone_mode:
            tags.append(
                {
                    "layer": "content",
                    "tag": "dual_route_text_split",
                    "route": "both",
                    "severity": "info",
                    "reason": f"基线使用 {baseline_mode}，克隆使用 {clone_mode}，可分离稳定性与控制收益。",
                }
            )
        if any(item.get("category") == "named_entity" for item in pronunciation_hits):
            tags.append(
                {
                    "layer": "pronunciation",
                    "tag": "named_entity_adjusted",
                    "route": "clone",
                    "severity": "medium",
                    "reason": "检测到专名词发音修正，需重点对听是否改善专名读法。",
                }
            )
        if any(item.get("category") in {"function_word", "connector"} for item in pronunciation_hits):
            tags.append(
                {
                    "layer": "pronunciation",
                    "tag": "function_word_adjusted",
                    "route": "clone",
                    "severity": "medium",
                    "reason": "检测到连接词或口语虚词被改写，需核对是否提升口语读感。",
                }
            )
        if any((item.get("category") == "connector") or ("连接词" in str(item.get("notes", ""))) for item in prosody_hits):
            tags.append(
                {
                    "layer": "prosody",
                    "tag": "connector_prosody_adjusted",
                    "route": "clone",
                    "severity": "medium",
                    "reason": "韵律层已介入连接词和停顿衔接，需关注句间是否更顺或出现生硬断点。",
                }
            )
        if voice_clone_enabled:
            tags.append(
                {
                    "layer": "clone_carrier",
                    "tag": "voice_clone_load",
                    "route": "clone",
                    "severity": "high" if clone_mode == "prosody_text" else "medium",
                    "reason": "克隆链路承担声纹承载任务，可能放大发音层或韵律层调整带来的失真。",
                }
            )
        if baseline_error:
            tags.append(
                {
                    "layer": "clone_carrier",
                    "tag": "baseline_generation_error",
                    "route": "baseline",
                    "severity": "high",
                    "reason": f"基线链路生成异常: {baseline_error}",
                }
            )
        if clone_error:
            tags.append(
                {
                    "layer": "clone_carrier",
                    "tag": "clone_generation_error",
                    "route": "clone",
                    "severity": "high",
                    "reason": f"克隆链路生成异常: {clone_error}",
                }
            )
        return tags

    def _summarize_issue_tags(self, issue_tags: list[dict[str, Any]]) -> str:
        if not issue_tags:
            return "当前未发现明显失真归因标签，建议直接做双路主观听感对比。"
        order = ["content", "pronunciation", "prosody", "clone_carrier"]
        labels = {
            "content": "内容层",
            "pronunciation": "发音层",
            "prosody": "韵律层",
            "clone_carrier": "克隆承载层",
        }
        seen: list[str] = []
        for layer in order:
            if any(item.get("layer") == layer for item in issue_tags):
                seen.append(labels[layer])
        return "、".join(seen) + "存在可解释差异，推荐按标签逐项试听。"

    def _build_voice_match_summary(
        self,
        *,
        teacher_route: dict[str, Any],
        voice_matched_route: dict[str, Any],
    ) -> dict[str, Any]:
        matched_ok = bool(voice_matched_route.get("wav_path")) and not voice_matched_route.get("error")
        provider = voice_matched_route.get("voice_clone_provider") or self.cfg.voice_conversion_provider
        if matched_ok:
            reason = "先听 gold teacher 确认粤语发音，再听 voice matched 判断音色迁移是否值得保留。"
        else:
            reason = "当前音色转换不可用或失败，主试听结果回退为 gold teacher。"
        return {
            "teacher_is_reference": True,
            "voice_matched_available": matched_ok,
            "voice_match_provider": provider or "none",
            "voice_match_error": voice_matched_route.get("error", ""),
            "recommendation_reason": reason,
        }

    def _pick_recommended_main_output(
        self,
        *,
        teacher_route: dict[str, Any],
        voice_matched_route: dict[str, Any],
    ) -> str:
        if voice_matched_route.get("wav_path") and not voice_matched_route.get("error"):
            return "voice_matched"
        return "gold_teacher"

    def process_text(
        self,
        text: str,
        *,
        enable_rewrite: bool = True,
        enable_tts: bool = True,
        segment_max_len: int = 28,
        voice: str | None = None,
        input_lang: str = "zh",
        voice_clone_enabled: bool = False,
        speaker_ref_audio: str = "",
    ) -> dict[str, Any]:
        trace_id = str(uuid.uuid4())
        t0 = perf_counter()
        review = review_asr_text_en(text, self.cfg) if input_lang == "en" else review_asr_text(text, self.cfg, input_lang=input_lang)
        review_text_value = review["asr_reviewed_text"]
        pivot_text_zh = ""
        translation_notes = ""
        if input_lang == "en":
            pivot = translate_en_to_pivot_zh(review_text_value, self.cfg)
            pivot_text_zh = pivot["pivot_text_zh"]
            translation_notes = pivot["translation_notes"]

        rewrite = None
        if enable_rewrite:
            rewrite = rewrite_text(
                review_text_value,
                self.cfg,
                segment_max_len=segment_max_len,
                input_lang=input_lang,
                pivot_text_zh=pivot_text_zh,
                target_dialect=self.cfg.default_target_dialect,
                dialect_style=self.cfg.default_dialect_style,
            )
            rewrite["translation_notes"] = translation_notes

        tts = None
        if enable_tts:
            target_text, tts_input_mode, clone_route_reason = self._resolve_clone_route_input(rewrite, review_text_value)
            baseline_text, baseline_input_mode, baseline_route_reason = self._resolve_baseline_route_input(rewrite, review_text_value)
            legacy_clone_wav_path = self._build_wav_path(trace_id)
            old_voice = self.cfg.qwen_tts_voice
            if voice:
                self.cfg.qwen_tts_voice = voice
            active_voice = self.cfg.qwen_tts_voice
            teacher_wav_path = self._build_wav_path(f"{trace_id}_gold_teacher")
            teacher_result = tts_gold_teacher(
                baseline_text,
                self.cfg,
                teacher_wav_path,
            )
            legacy_clone_result = tts_text(
                target_text,
                self.cfg,
                legacy_clone_wav_path,
                voice_clone_enabled=voice_clone_enabled,
                speaker_ref_audio=speaker_ref_audio,
                preferred_name=f"vc_{uuid.uuid4().hex[:8]}",
            )
            voice_matched_wav_path = self._build_wav_path(f"{trace_id}_voice_matched")
            if voice_clone_enabled and speaker_ref_audio and teacher_result.get("wav_path"):
                voice_matched_result = tts_voice_match_from_teacher(
                    teacher_result.get("wav_path", ""),
                    self.cfg,
                    voice_matched_wav_path,
                    speaker_ref_audio=speaker_ref_audio,
                    preferred_name=f"vm_{uuid.uuid4().hex[:8]}",
                )
            else:
                voice_matched_result = {
                    "wav_path": "",
                    "audio_url": "",
                    "expires_at": "",
                    "error": "voice match disabled or reference audio missing",
                    "voice_clone_provider": self.cfg.voice_conversion_provider,
                    "fallback_reason": "voice_match_disabled",
                    "latency_ms": 0.0,
                    "speaker_similarity_note": "未执行音色转换，当前保留 gold teacher 作为主试听结果",
                    "speaker_similarity_priority": self.cfg.speaker_similarity_priority,
                    "tts_fluency_mode": self.cfg.tts_fluency_mode,
                    "tts_style_instructions": self.cfg.tts_style_instructions,
                    "instruction_mode_active": False,
                }
            self.cfg.qwen_tts_voice = old_voice
            legacy_clone_route = self._build_route_payload(
                "legacy_text_clone",
                legacy_clone_result,
                input_text=target_text,
                input_mode=tts_input_mode,
                route_reason=clone_route_reason,
                default_voice=active_voice,
                voice_clone_enabled=voice_clone_enabled,
            )
            teacher_route = self._build_route_payload(
                "gold_teacher",
                teacher_result,
                input_text=baseline_text,
                input_mode=baseline_input_mode,
                route_reason="gold teacher 固定作为系统粤语发音金标准，只负责“怎么说”。",
                default_voice=active_voice,
                voice_clone_enabled=False,
            )
            teacher_route["route_role"] = "gold_standard_pronunciation"
            voice_matched_route = self._build_route_payload(
                "voice_matched",
                voice_matched_result,
                input_text=baseline_text,
                input_mode="teacher_audio_to_audio",
                route_reason="voice matched 只负责“像谁说”，基于 gold teacher 音频做音色转换，不再决定发音内容。",
                default_voice=active_voice,
                voice_clone_enabled=bool(voice_clone_enabled and speaker_ref_audio),
            )
            voice_matched_route["tts_model"] = voice_matched_result.get("model", self.cfg.voice_conversion_model)
            voice_matched_route["voice_clone_provider"] = voice_matched_result.get("voice_clone_provider") or self.cfg.voice_conversion_provider
            voice_matched_route["route_role"] = "voice_identity_transfer"
            gap_summary = self._build_gap_summary(
                baseline_route=teacher_route,
                clone_route=legacy_clone_route,
                rewrite=rewrite,
                voice_clone_enabled=voice_clone_enabled,
            )
            voice_match_summary = self._build_voice_match_summary(
                teacher_route=teacher_route,
                voice_matched_route=voice_matched_route,
            )
            recommended_main_output = self._pick_recommended_main_output(
                teacher_route=teacher_route,
                voice_matched_route=voice_matched_route,
            )
            gap_summary["recommended_route"] = recommended_main_output
            gap_summary["recommended_reason"] = voice_match_summary["recommendation_reason"]
            tts = {
                "wav_path": legacy_clone_route["wav_path"],
                "audio_url": legacy_clone_route["audio_url"],
                "expires_at": legacy_clone_route["expires_at"],
                "tts_model": legacy_clone_route["tts_model"],
                "tts_voice": legacy_clone_route["tts_voice"],
                "latency_ms": legacy_clone_route["latency_ms"],
                "error": legacy_clone_route["error"],
                "voice_clone_enabled": legacy_clone_route["voice_clone_enabled"],
                "voice_clone_provider": legacy_clone_route["voice_clone_provider"],
                "speaker_similarity_note": legacy_clone_route["speaker_similarity_note"],
                "clone_mode": legacy_clone_route["clone_mode"],
                "fallback_reason": legacy_clone_route["fallback_reason"],
                "speaker_similarity_priority": legacy_clone_route["speaker_similarity_priority"],
                "tts_fluency_mode": legacy_clone_route["tts_fluency_mode"],
                "tts_style_instructions": legacy_clone_route["tts_style_instructions"],
                "instruction_mode_active": legacy_clone_route["instruction_mode_active"],
                "tts_input_text": legacy_clone_route["input_text"],
                "tts_input_mode": legacy_clone_route["input_mode"],
                "audio_meta": legacy_clone_route["audio_meta"],
                "baseline_wav_path": teacher_route["wav_path"],
                "baseline_audio_url": teacher_route["audio_url"],
                "baseline_tts_model": teacher_route["tts_model"],
                "baseline_tts_voice": teacher_route["tts_voice"],
                "baseline_error": teacher_route["error"],
                "baseline_tts_input_text": teacher_route["input_text"],
                "baseline_tts_input_mode": teacher_route["input_mode"],
                "baseline_audio_meta": teacher_route["audio_meta"],
                "baseline": teacher_route,
                "clone": legacy_clone_route,
                "gap_summary": gap_summary,
                "gold_teacher": teacher_route,
                "voice_matched": voice_matched_route,
                "legacy_text_clone": legacy_clone_route,
                "recommended_main_output": recommended_main_output,
                "voice_match_summary": voice_match_summary,
                "timbre_ref_audio": str(speaker_ref_audio) if speaker_ref_audio else "",
                "prosody_ref_audio": "",
                "prosody_guidance_mode": "",
            }

        return {
            "source_audio": None,
            "asr": None,
            "review": review,
            "rewrite": rewrite,
            "tts": tts,
            "trace_id": trace_id,
            "total_latency_ms": round((perf_counter() - t0) * 1000, 2),
            "input_lang": input_lang,
            "pivot_text_zh": pivot_text_zh,
        }

    def process_audio(
        self,
        wav_path: str | Path,
        *,
        enable_punc: bool = True,
        enable_rewrite: bool = True,
        enable_tts: bool = True,
        segment_max_len: int = 28,
        voice: str | None = None,
        voice_clone_enabled: bool = False,
        speaker_ref_audio: str = "",
    ) -> dict[str, Any]:
        trace_id = str(uuid.uuid4())
        t0 = perf_counter()
        try:
            asr_result = get_asr_system_engine().process_file(wav_path, enable_vad=True, enable_lid=True, enable_punc=enable_punc)
        except Exception:
            asr_result = get_asr_engine().transcribe_file(wav_path, enable_punc=enable_punc, return_timestamp=True)
            asr_result["detected_languages"] = []
            asr_result["vad_segments_ms"] = []
            asr_result["sentences"] = []
            asr_result["words"] = []
        asr_text = asr_result.get("punc_text") or asr_result.get("text", "")
        input_lang = self._pick_input_lang(asr_result)
        review = review_asr_text_en(asr_text, self.cfg) if input_lang == "en" else review_asr_text(asr_text, self.cfg, input_lang=input_lang)
        pivot_text_zh = ""
        translation_notes = ""
        if input_lang == "en":
            pivot = translate_en_to_pivot_zh(review["asr_reviewed_text"], self.cfg)
            pivot_text_zh = pivot["pivot_text_zh"]
            translation_notes = pivot["translation_notes"]
        rewrite = (
            rewrite_text(
                review["asr_reviewed_text"],
                self.cfg,
                segment_max_len=segment_max_len,
                input_lang=input_lang,
                pivot_text_zh=pivot_text_zh,
                target_dialect=self.cfg.default_target_dialect,
                dialect_style=self.cfg.default_dialect_style,
            )
            if enable_rewrite
            else None
        )
        if rewrite:
            rewrite["translation_notes"] = translation_notes

        tts = None
        if enable_tts:
            target_text, tts_input_mode, clone_route_reason = self._resolve_clone_route_input(rewrite, review["asr_reviewed_text"])
            baseline_text, baseline_input_mode, baseline_route_reason = self._resolve_baseline_route_input(rewrite, review["asr_reviewed_text"])
            legacy_clone_wav_out = self._build_wav_path(Path(wav_path).stem)
            old_voice = self.cfg.qwen_tts_voice
            if voice:
                self.cfg.qwen_tts_voice = voice
            active_voice = self.cfg.qwen_tts_voice
            teacher_wav_out = self._build_wav_path(f"{Path(wav_path).stem}_gold_teacher")
            teacher_result = tts_gold_teacher(
                baseline_text,
                self.cfg,
                teacher_wav_out,
            )
            legacy_clone_result = tts_text(
                target_text,
                self.cfg,
                legacy_clone_wav_out,
                voice_clone_enabled=voice_clone_enabled,
                speaker_ref_audio=speaker_ref_audio,
                preferred_name=f"vc_{uuid.uuid4().hex[:8]}",
            )
            voice_matched_wav_out = self._build_wav_path(f"{Path(wav_path).stem}_voice_matched")
            if voice_clone_enabled and speaker_ref_audio and teacher_result.get("wav_path"):
                voice_matched_result = tts_voice_match_from_teacher(
                    teacher_result.get("wav_path", ""),
                    self.cfg,
                    voice_matched_wav_out,
                    speaker_ref_audio=speaker_ref_audio,
                    preferred_name=f"vm_{uuid.uuid4().hex[:8]}",
                )
            else:
                voice_matched_result = {
                    "wav_path": "",
                    "audio_url": "",
                    "expires_at": "",
                    "error": "voice match disabled or reference audio missing",
                    "voice_clone_provider": self.cfg.voice_conversion_provider,
                    "fallback_reason": "voice_match_disabled",
                    "latency_ms": 0.0,
                    "speaker_similarity_note": "未执行音色转换，当前保留 gold teacher 作为主试听结果",
                    "speaker_similarity_priority": self.cfg.speaker_similarity_priority,
                    "tts_fluency_mode": self.cfg.tts_fluency_mode,
                    "tts_style_instructions": self.cfg.tts_style_instructions,
                    "instruction_mode_active": False,
                }
            self.cfg.qwen_tts_voice = old_voice
            legacy_clone_route = self._build_route_payload(
                "legacy_text_clone",
                legacy_clone_result,
                input_text=target_text,
                input_mode=tts_input_mode,
                route_reason=clone_route_reason,
                default_voice=active_voice,
                voice_clone_enabled=voice_clone_enabled,
            )
            teacher_route = self._build_route_payload(
                "gold_teacher",
                teacher_result,
                input_text=baseline_text,
                input_mode=baseline_input_mode,
                route_reason="gold teacher 固定作为系统粤语发音金标准，只负责“怎么说”。",
                default_voice=active_voice,
                voice_clone_enabled=False,
            )
            teacher_route["route_role"] = "gold_standard_pronunciation"
            voice_matched_route = self._build_route_payload(
                "voice_matched",
                voice_matched_result,
                input_text=baseline_text,
                input_mode="teacher_audio_to_audio",
                route_reason="voice matched 只负责“像谁说”，基于 gold teacher 音频做音色转换，不再决定发音内容。",
                default_voice=active_voice,
                voice_clone_enabled=bool(voice_clone_enabled and speaker_ref_audio),
            )
            voice_matched_route["tts_model"] = voice_matched_result.get("model", self.cfg.voice_conversion_model)
            voice_matched_route["voice_clone_provider"] = voice_matched_result.get("voice_clone_provider") or self.cfg.voice_conversion_provider
            voice_matched_route["route_role"] = "voice_identity_transfer"
            gap_summary = self._build_gap_summary(
                baseline_route=teacher_route,
                clone_route=legacy_clone_route,
                rewrite=rewrite,
                voice_clone_enabled=voice_clone_enabled,
            )
            voice_match_summary = self._build_voice_match_summary(
                teacher_route=teacher_route,
                voice_matched_route=voice_matched_route,
            )
            recommended_main_output = self._pick_recommended_main_output(
                teacher_route=teacher_route,
                voice_matched_route=voice_matched_route,
            )
            gap_summary["recommended_route"] = recommended_main_output
            gap_summary["recommended_reason"] = voice_match_summary["recommendation_reason"]
            tts = {
                "wav_path": legacy_clone_route["wav_path"],
                "audio_url": legacy_clone_route["audio_url"],
                "expires_at": legacy_clone_route["expires_at"],
                "tts_model": legacy_clone_route["tts_model"],
                "tts_voice": legacy_clone_route["tts_voice"],
                "latency_ms": legacy_clone_route["latency_ms"],
                "error": legacy_clone_route["error"],
                "voice_clone_enabled": legacy_clone_route["voice_clone_enabled"],
                "voice_clone_provider": legacy_clone_route["voice_clone_provider"],
                "speaker_similarity_note": legacy_clone_route["speaker_similarity_note"],
                "clone_mode": legacy_clone_route["clone_mode"],
                "fallback_reason": legacy_clone_route["fallback_reason"],
                "speaker_similarity_priority": legacy_clone_route["speaker_similarity_priority"],
                "tts_fluency_mode": legacy_clone_route["tts_fluency_mode"],
                "tts_style_instructions": legacy_clone_route["tts_style_instructions"],
                "instruction_mode_active": legacy_clone_route["instruction_mode_active"],
                "tts_input_text": legacy_clone_route["input_text"],
                "tts_input_mode": legacy_clone_route["input_mode"],
                "audio_meta": legacy_clone_route["audio_meta"],
                "baseline_wav_path": teacher_route["wav_path"],
                "baseline_audio_url": teacher_route["audio_url"],
                "baseline_tts_model": teacher_route["tts_model"],
                "baseline_tts_voice": teacher_route["tts_voice"],
                "baseline_error": teacher_route["error"],
                "baseline_tts_input_text": teacher_route["input_text"],
                "baseline_tts_input_mode": teacher_route["input_mode"],
                "baseline_audio_meta": teacher_route["audio_meta"],
                "baseline": teacher_route,
                "clone": legacy_clone_route,
                "gap_summary": gap_summary,
                "gold_teacher": teacher_route,
                "voice_matched": voice_matched_route,
                "legacy_text_clone": legacy_clone_route,
                "recommended_main_output": recommended_main_output,
                "voice_match_summary": voice_match_summary,
                "timbre_ref_audio": str(speaker_ref_audio) if speaker_ref_audio else "",
                "prosody_ref_audio": "",
                "prosody_guidance_mode": "",
            }

        return {
            "source_audio": {"path": str(Path(wav_path).resolve())},
            "asr": asr_result,
            "review": review,
            "rewrite": rewrite,
            "tts": tts,
            "trace_id": trace_id,
            "total_latency_ms": round((perf_counter() - t0) * 1000, 2),
            "input_lang": input_lang,
            "pivot_text_zh": pivot_text_zh,
        }

    def _build_wav_path(self, stem: str) -> Path:
        return self.cfg.output_dir / "audio" / f"{stem}.wav"

    def _audio_meta(self, wav_path: str) -> dict[str, Any] | None:
        if not wav_path:
            return None
        p = Path(wav_path)
        if not p.exists():
            return None
        info = sf.info(str(p))
        return {
            "size_bytes": p.stat().st_size,
            "duration_s": round(float(info.duration), 3),
            "sample_rate": info.samplerate,
            "channels": info.channels,
        }

    def _pick_input_lang(self, asr_result: dict[str, Any]) -> str:
        langs = asr_result.get("detected_languages") or []
        if langs:
            primary = str(langs[0].get("lang", "")).lower()
            if primary.startswith("en"):
                return "en"
            if primary.startswith("zh"):
                return "zh"
        text = str(asr_result.get("text", ""))
        if any("a" <= c.lower() <= "z" for c in text):
            return "en"
        return "zh"


_ENGINE: DialectPipelineEngine | None = None


def get_pipeline_engine() -> DialectPipelineEngine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = DialectPipelineEngine()
    return _ENGINE
