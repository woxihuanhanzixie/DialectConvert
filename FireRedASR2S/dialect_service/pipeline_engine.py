from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from pathlib import Path
from time import perf_counter
from typing import Any

import soundfile as sf

from asr_service.audio_io import make_temp_dir, normalize_file_to_wav
from asr_service.asr_engine import get_asr_engine
from asr_service.cloud_asr import transcribe_api_first
from asr_service.config import AsrServiceConfig
from asr_service.system_engine import get_asr_system_engine
from fireredasr2s.dialect_pipeline.config import Step2Config
from fireredasr2s.dialect_pipeline.dialects import dialect_label, normalize_dialect_style

from .adapters import (
    review_asr_text,
    review_asr_text_en,
    rewrite_text,
    translate_en_to_pivot_zh,
    tts_gold_teacher,
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
            "voice_match_provider": self.cfg.voice_conversion_provider,
            "qwen_voice_enrollment_model": self.cfg.qwen_voice_enrollment_model,
            "qwen_voice_target_model": self.cfg.qwen_voice_target_model,
            "output_dir": str(self.cfg.output_dir),
        }

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

    def _semantic_tts_input(self, review_text: str, pivot_text_zh: str = "") -> tuple[str, str, str]:
        text = (pivot_text_zh or review_text or "").strip()
        mode = "semantic_text" if text else "review_text"
        reason = "Gold Teacher 和 Voice Matched 固定消费语义普通话文本；方言转写只用于页面展示，不参与 TTS。"
        return text, mode, reason

    def _teacher_tts_input(
        self,
        rewrite: dict[str, Any] | None,
        review_text: str,
        pivot_text_zh: str = "",
    ) -> tuple[str, str, str, bool]:
        if rewrite:
            for key, mode, label in (
                ("prosody_text", "prosody_text", "韵律润色文本"),
                ("pronunciation_text", "pronunciation_text", "发音转写文本"),
                ("dialect_text", "dialect_text", "方言发声文本"),
            ):
                text = str(rewrite.get(key) or "").strip()
                if text:
                    return (
                        text,
                        mode,
                        f"Gold Teacher 使用{label}生成准确方言发音和韵律；Voice Matched 只跟随该 teacher 音频做音色迁移。",
                        True,
                    )
        text = (pivot_text_zh or review_text or "").strip()
        mode = "semantic_text" if text else "review_text"
        return (
            text,
            mode,
            "未获得可发声方言文本，Gold Teacher 只能回退到语义文本；Voice Matched 不会用文本复刻冒充音色迁移。",
            False,
        )

    def _await_rewrite_for_teacher(
        self,
        rewrite_future,
        rewrite_executor: ThreadPoolExecutor | None,
        *,
        translation_notes: str,
    ) -> dict[str, Any] | None:
        if rewrite_future is None:
            return None
        try:
            rewrite = rewrite_future.result(timeout=max(1, int(self.cfg.timeout_s)))
            rewrite["translation_notes"] = translation_notes
            return rewrite
        except Exception as exc:  # noqa: BLE001
            return {
                "dialect_text": "",
                "semantic_text": "",
                "pronunciation_text": "",
                "prosody_text": "",
                "target_dialect": self.cfg.default_target_dialect,
                "dialect_style": self.cfg.default_dialect_style,
                "llm_latency_ms": 0.0,
                "display_only": False,
                "display_rewrite_status": "failed_before_teacher",
                "llm_error": str(exc),
                "translation_notes": translation_notes,
            }
        finally:
            if rewrite_executor is not None:
                rewrite_executor.shutdown(wait=False)

    def _finish_display_rewrite(
        self,
        rewrite_future,
        rewrite_executor: ThreadPoolExecutor | None,
        *,
        translation_notes: str,
        timeout_s: float = 0.2,
    ) -> dict[str, Any] | None:
        if rewrite_future is None:
            return None
        try:
            rewrite = rewrite_future.result(timeout=timeout_s)
            rewrite["translation_notes"] = translation_notes
            return rewrite
        except TimeoutError:
            return {
                "dialect_text": "方言展示文本仍在生成，主音频链路未等待该步骤。",
                "semantic_text": "方言展示文本仍在生成，主音频链路未等待该步骤。",
                "pronunciation_text": "",
                "prosody_text": "",
                "target_dialect": self.cfg.default_target_dialect,
                "dialect_style": self.cfg.default_dialect_style,
                "llm_latency_ms": 0.0,
                "display_only": True,
                "display_rewrite_status": "timeout_not_blocking_audio",
                "translation_notes": translation_notes,
            }
        finally:
            if rewrite_executor is not None:
                rewrite_executor.shutdown(wait=False)

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
        teacher_route: dict[str, Any],
        voice_matched_route: dict[str, Any],
    ) -> dict[str, Any]:
        teacher_mode = teacher_route.get("input_mode") or "review_text"
        matched_available = bool(voice_matched_route.get("wav_path")) and not voice_matched_route.get("error")
        voice_match_error = voice_matched_route.get("error") or ""
        voice_match_provider = (voice_matched_route.get("voice_clone_provider") or self.cfg.voice_conversion_provider or "").strip().lower()
        qwen_voice_clone_active = voice_match_provider in {"qwen_voice_clone", "qwen_vc", "qwen"}

        if qwen_voice_clone_active:
            content_diff = "Gold Teacher 与 Voice Matched 共享同一份语义确认文本，差异主要来自 Qwen 复刻音色。"
            pronunciation_diff = "Voice Matched 使用与音色创建 target_model 一致的 Qwen VC 模型合成，尽量继承中间层确认后的发音目标。"
        else:
            content_diff = "Gold Teacher 与 Voice Matched 共享同一份 teacher 音频内容，差异主要来自音色迁移。"
            pronunciation_diff = "Voice Matched 基于 Gold Teacher 音频做转换，不再单独改写文本或重做发音。"
        if matched_available:
            fluency_diff = "Voice Matched 额外承担音色迁移，可能引入轻微失真；Gold Teacher 通常更稳。"
        else:
            fluency_diff = "当前 Voice Matched 不可用，主试听结果回退为 Gold Teacher。"

        route_summary = f"Gold Teacher 固定负责“怎么说”，输入层为 {teacher_mode}；"
        if qwen_voice_clone_active:
            route_summary += "Voice Matched 只负责“像谁说”，优先通过 Qwen 声音复刻 API 生成。"
        else:
            route_summary += "Voice Matched 只负责“像谁说”，基于 teacher 音频做音色转换。"
        processing_split = (
            "文本改写、发音与韵律控制由 LLM 中间层和 Gold Teacher 承担；音色相似度由 Qwen voice enrollment 与 VC 合成承担。"
            if qwen_voice_clone_active
            else "文本改写、发音与韵律控制由 Gold Teacher 完成；音色相似度由 Voice Matched 承担。"
        )
        issue_tags: list[dict[str, Any]] = []
        if teacher_route.get("error"):
            issue_tags.append(
                {
                    "layer": "content",
                    "tag": "teacher_generation_error",
                    "route": "gold_teacher",
                    "severity": "high",
                    "reason": f"Gold Teacher 生成异常: {teacher_route.get('error')}",
                }
            )
        if voice_match_error:
            issue_tags.append(
                {
                    "layer": "clone_carrier",
                    "tag": "voice_match_error",
                    "route": "voice_matched",
                    "severity": "high",
                    "reason": f"Voice Matched 生成异常: {voice_match_error}",
                }
            )
        elif voice_matched_route.get("voice_clone_enabled"):
            issue_tags.append(
                {
                    "layer": "clone_carrier",
                    "tag": "voice_match_active",
                    "route": "voice_matched",
                    "severity": "medium",
                    "reason": "Voice Matched 已启用，需重点对听音色相似度与自然度损失。",
                }
            )
        issue_tag_summary = self._summarize_issue_tags(issue_tags)

        recommended_route = "voice_matched" if matched_available else "gold_teacher"
        recommended_strategy = "先听 Gold Teacher 确认发音，再听 Voice Matched 判断音色迁移是否值得保留。"
        recommended_reason = "Voice Matched 只在成功生成时作为主输出，否则保持 Gold Teacher 兜底。"
        baseline_advantage = "Gold Teacher 不承担音色迁移，通常在发音稳定性和流畅度上更可靠。"
        clone_weakness = (
            "Voice Matched 依赖参考音频质量和 Qwen 声音复刻接口，可能增加耗时；失败时必须清楚回退 Gold Teacher。"
            if qwen_voice_clone_active
            else "Voice Matched 依赖额外的音色转换步骤，可能增加耗时并引入轻微失真。"
        )

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
            reason = "先听 gold teacher 确认方言发音，再听 voice matched 判断音色迁移是否值得保留。"
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
        target_dialect: str | None = None,
        dialect_style: str | None = None,
    ) -> dict[str, Any]:
        trace_id = str(uuid.uuid4())
        t0 = perf_counter()
        active_target_dialect = target_dialect or self.cfg.default_target_dialect
        active_dialect_style = normalize_dialect_style(active_target_dialect, dialect_style or self.cfg.default_dialect_style)
        active_dialect_label = dialect_label(active_target_dialect, active_dialect_style)
        self.cfg.default_target_dialect = active_target_dialect
        self.cfg.default_dialect_style = active_dialect_style
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
                target_dialect=active_target_dialect,
                dialect_style=active_dialect_style,
            )
            rewrite["translation_notes"] = translation_notes

        tts = None
        if enable_tts:
            baseline_text, baseline_input_mode, baseline_reason, has_teacher_control_text = self._teacher_tts_input(
                rewrite,
                review_text_value,
                pivot_text_zh,
            )
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
            voice_matched_wav_path = self._build_wav_path(f"{trace_id}_voice_matched")
            voice_match_requested = bool(speaker_ref_audio and (voice_clone_enabled or speaker_ref_audio))
            active_voice_match_provider = (self.cfg.voice_conversion_provider or "").strip().lower()
            qwen_voice_match_provider = active_voice_match_provider in {"qwen_voice_clone", "qwen_vc", "qwen"}
            if qwen_voice_match_provider:
                voice_matched_result = {
                    "wav_path": "",
                    "audio_url": "",
                    "expires_at": "",
                    "error": "qwen_voice_clone is text-to-speech cloning and cannot be used as teacher-first Voice Matched.",
                    "voice_clone_provider": active_voice_match_provider,
                    "fallback_reason": "qwen_text_clone_not_teacher_audio_to_audio",
                    "latency_ms": 0.0,
                    "speaker_similarity_note": "Qwen text clone is comparison only; Voice Matched must follow Gold Teacher audio.",
                    "speaker_similarity_priority": self.cfg.speaker_similarity_priority,
                    "tts_fluency_mode": self.cfg.tts_fluency_mode,
                    "tts_style_instructions": self.cfg.tts_style_instructions,
                    "instruction_mode_active": False,
                }
            elif voice_match_requested and teacher_result.get("wav_path") and has_teacher_control_text:
                voice_matched_result = tts_voice_match_from_teacher(
                    teacher_result.get("wav_path", ""),
                    self.cfg,
                    voice_matched_wav_path,
                    speaker_ref_audio=speaker_ref_audio,
                    preferred_name=f"vm_{uuid.uuid4().hex[:8]}",
                    input_text="",
                )
            else:
                fallback_reason = "voice_match_disabled"
                fallback_error = "voice match disabled or reference audio missing"
                if voice_match_requested and not has_teacher_control_text:
                    fallback_reason = "missing_dialect_teacher_text"
                    fallback_error = "missing dialect/prosody teacher text; refusing to synthesize text clone as Voice Matched"
                voice_matched_result = {
                    "wav_path": "",
                    "audio_url": "",
                    "expires_at": "",
                    "error": fallback_error,
                    "voice_clone_provider": self.cfg.voice_conversion_provider,
                    "fallback_reason": fallback_reason,
                    "latency_ms": 0.0,
                    "speaker_similarity_note": "未执行音色转换，当前保留 gold teacher 作为主试听结果",
                    "speaker_similarity_priority": self.cfg.speaker_similarity_priority,
                    "tts_fluency_mode": self.cfg.tts_fluency_mode,
                    "tts_style_instructions": self.cfg.tts_style_instructions,
                    "instruction_mode_active": False,
                }
            self.cfg.qwen_tts_voice = old_voice
            teacher_route = self._build_route_payload(
                "gold_teacher",
                teacher_result,
                input_text=baseline_text,
                input_mode=baseline_input_mode,
                route_reason=f"gold teacher 固定作为系统{active_dialect_label}发音参考，只负责“怎么说”。{baseline_reason}",
                default_voice=active_voice,
                voice_clone_enabled=False,
            )
            teacher_route["route_role"] = "gold_standard_pronunciation"
            voice_match_input_mode = "teacher_audio_to_audio"
            voice_match_reason = (
                "voice matched 调用 Qwen 声音复刻 API，用参考音频创建或复用专属音色后合成最终音频。"
                if voice_match_input_mode == "semantic_text_with_cloned_voice"
                else "voice matched 只负责“像谁说”，基于 gold teacher 音频做音色转换，不再决定发音内容。"
            )
            voice_matched_route = self._build_route_payload(
                "voice_matched",
                voice_matched_result,
                input_text=teacher_result.get("wav_path", ""),
                input_mode=voice_match_input_mode,
                route_reason=voice_match_reason,
                default_voice=active_voice,
                voice_clone_enabled=voice_match_requested,
            )
            voice_matched_route["tts_model"] = voice_matched_result.get("model", self.cfg.voice_conversion_model)
            voice_matched_route["voice_clone_provider"] = voice_matched_result.get("voice_clone_provider") or self.cfg.voice_conversion_provider
            voice_matched_route["route_role"] = "voice_identity_transfer"
            gap_summary = self._build_gap_summary(
                teacher_route=teacher_route,
                voice_matched_route=voice_matched_route,
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
            primary_route = voice_matched_route if recommended_main_output == "voice_matched" else teacher_route
            tts = {
                "wav_path": primary_route["wav_path"],
                "audio_url": primary_route["audio_url"],
                "expires_at": primary_route["expires_at"],
                "tts_model": primary_route["tts_model"],
                "tts_voice": primary_route["tts_voice"],
                "latency_ms": round(float(teacher_route["latency_ms"]) + float(voice_matched_route["latency_ms"]), 2),
                "error": primary_route["error"],
                "voice_clone_enabled": voice_matched_route["voice_clone_enabled"],
                "voice_clone_provider": voice_matched_route["voice_clone_provider"],
                "speaker_similarity_note": primary_route["speaker_similarity_note"],
                "clone_mode": primary_route["clone_mode"],
                "fallback_reason": primary_route["fallback_reason"],
                "speaker_similarity_priority": primary_route["speaker_similarity_priority"],
                "tts_fluency_mode": primary_route["tts_fluency_mode"],
                "tts_style_instructions": primary_route["tts_style_instructions"],
                "instruction_mode_active": primary_route["instruction_mode_active"],
                "tts_input_text": teacher_route["input_text"],
                "tts_input_mode": teacher_route["input_mode"],
                "audio_meta": primary_route["audio_meta"],
                "baseline_wav_path": teacher_route["wav_path"],
                "baseline_audio_url": teacher_route["audio_url"],
                "baseline_tts_model": teacher_route["tts_model"],
                "baseline_tts_voice": teacher_route["tts_voice"],
                "baseline_error": teacher_route["error"],
                "baseline_tts_input_text": teacher_route["input_text"],
                "baseline_tts_input_mode": teacher_route["input_mode"],
                "baseline_audio_meta": teacher_route["audio_meta"],
                "baseline": teacher_route,
                "clone": voice_matched_route,
                "gap_summary": gap_summary,
                "gold_teacher": teacher_route,
                "voice_matched": voice_matched_route,
                "legacy_text_clone": None,
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
        target_dialect: str | None = None,
        dialect_style: str | None = None,
    ) -> dict[str, Any]:
        trace_id = str(uuid.uuid4())
        t0 = perf_counter()
        active_target_dialect = target_dialect or self.cfg.default_target_dialect
        active_dialect_style = normalize_dialect_style(active_target_dialect, dialect_style or self.cfg.default_dialect_style)
        active_dialect_label = dialect_label(active_target_dialect, active_dialect_style)
        self.cfg.default_target_dialect = active_target_dialect
        self.cfg.default_dialect_style = active_dialect_style
        asr_cfg = AsrServiceConfig.from_env()
        asr_result, cloud_asr_error = transcribe_api_first(
            wav_path,
            asr_cfg,
            enable_punc=enable_punc,
            return_timestamp=True,
        )
        if asr_result is None:
            local_asr_path = Path(wav_path)
            if local_asr_path.suffix.lower() != ".wav":
                local_asr_path, _ = normalize_file_to_wav(
                    local_asr_path,
                    make_temp_dir(prefix="demo1_local_asr_fallback_"),
                )
            try:
                asr_result = get_asr_system_engine().process_file(local_asr_path, enable_vad=True, enable_lid=True, enable_punc=enable_punc)
                asr_result["asr_provider"] = "local_firered_system"
            except Exception:
                asr_result = get_asr_engine().transcribe_file(local_asr_path, enable_punc=enable_punc, return_timestamp=True)
                asr_result["detected_languages"] = []
                asr_result["vad_segments_ms"] = []
                asr_result["sentences"] = []
                asr_result["words"] = []
                asr_result["asr_provider"] = "local_firered_plain"
            asr_result["cloud_asr_error"] = cloud_asr_error
        asr_text = asr_result.get("punc_text") or asr_result.get("text", "")
        input_lang = self._pick_input_lang(asr_result)
        review = review_asr_text_en(asr_text, self.cfg) if input_lang == "en" else review_asr_text(asr_text, self.cfg, input_lang=input_lang)
        pivot_text_zh = ""
        translation_notes = ""
        if input_lang == "en":
            pivot = translate_en_to_pivot_zh(review["asr_reviewed_text"], self.cfg)
            pivot_text_zh = pivot["pivot_text_zh"]
            translation_notes = pivot["translation_notes"]
        rewrite = None
        rewrite_executor: ThreadPoolExecutor | None = None
        rewrite_future = None
        if enable_rewrite:
            rewrite_executor = ThreadPoolExecutor(max_workers=1)
            rewrite_future = rewrite_executor.submit(
                rewrite_text,
                review["asr_reviewed_text"],
                self.cfg,
                segment_max_len=segment_max_len,
                input_lang=input_lang,
                pivot_text_zh=pivot_text_zh,
                target_dialect=active_target_dialect,
                dialect_style=active_dialect_style,
            )

        tts = None
        if enable_tts:
            rewrite = self._await_rewrite_for_teacher(
                rewrite_future,
                rewrite_executor,
                translation_notes=translation_notes,
            )
            rewrite_future = None
            rewrite_executor = None
            baseline_text, baseline_input_mode, baseline_reason, has_teacher_control_text = self._teacher_tts_input(
                rewrite,
                review["asr_reviewed_text"],
                pivot_text_zh,
            )
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
            voice_matched_wav_out = self._build_wav_path(f"{Path(wav_path).stem}_voice_matched")
            voice_match_requested = bool(speaker_ref_audio and (voice_clone_enabled or speaker_ref_audio))
            active_voice_match_provider = (self.cfg.voice_conversion_provider or "").strip().lower()
            qwen_voice_match_provider = active_voice_match_provider in {"qwen_voice_clone", "qwen_vc", "qwen"}
            if qwen_voice_match_provider:
                voice_matched_result = {
                    "wav_path": "",
                    "audio_url": "",
                    "expires_at": "",
                    "error": "qwen_voice_clone is text-to-speech cloning and cannot be used as teacher-first Voice Matched.",
                    "voice_clone_provider": active_voice_match_provider,
                    "fallback_reason": "qwen_text_clone_not_teacher_audio_to_audio",
                    "latency_ms": 0.0,
                    "speaker_similarity_note": "Qwen text clone is comparison only; Voice Matched must follow Gold Teacher audio.",
                    "speaker_similarity_priority": self.cfg.speaker_similarity_priority,
                    "tts_fluency_mode": self.cfg.tts_fluency_mode,
                    "tts_style_instructions": self.cfg.tts_style_instructions,
                    "instruction_mode_active": False,
                }
            elif voice_match_requested and teacher_result.get("wav_path") and has_teacher_control_text:
                voice_matched_result = tts_voice_match_from_teacher(
                    teacher_result.get("wav_path", ""),
                    self.cfg,
                    voice_matched_wav_out,
                    speaker_ref_audio=speaker_ref_audio,
                    preferred_name=f"vm_{uuid.uuid4().hex[:8]}",
                    input_text="",
                )
            else:
                fallback_reason = "voice_match_disabled"
                fallback_error = "voice match disabled or reference audio missing"
                if voice_match_requested and not has_teacher_control_text:
                    fallback_reason = "missing_dialect_teacher_text"
                    fallback_error = "missing dialect/prosody teacher text; refusing to synthesize text clone as Voice Matched"
                voice_matched_result = {
                    "wav_path": "",
                    "audio_url": "",
                    "expires_at": "",
                    "error": fallback_error,
                    "voice_clone_provider": self.cfg.voice_conversion_provider,
                    "fallback_reason": fallback_reason,
                    "latency_ms": 0.0,
                    "speaker_similarity_note": "未执行音色转换，当前保留 gold teacher 作为主试听结果",
                    "speaker_similarity_priority": self.cfg.speaker_similarity_priority,
                    "tts_fluency_mode": self.cfg.tts_fluency_mode,
                    "tts_style_instructions": self.cfg.tts_style_instructions,
                    "instruction_mode_active": False,
                }
            self.cfg.qwen_tts_voice = old_voice
            teacher_route = self._build_route_payload(
                "gold_teacher",
                teacher_result,
                input_text=baseline_text,
                input_mode=baseline_input_mode,
                route_reason=f"gold teacher 固定作为系统{active_dialect_label}发音参考，只负责“怎么说”。{baseline_reason}",
                default_voice=active_voice,
                voice_clone_enabled=False,
            )
            teacher_route["route_role"] = "gold_standard_pronunciation"
            voice_match_input_mode = "teacher_audio_to_audio"
            voice_match_reason = (
                "voice matched 调用 Qwen 声音复刻 API，用参考音频创建或复用专属音色后合成最终音频。"
                if voice_match_input_mode == "semantic_text_with_cloned_voice"
                else "voice matched 只负责“像谁说”，基于 gold teacher 音频做音色转换，不再决定发音内容。"
            )
            voice_matched_route = self._build_route_payload(
                "voice_matched",
                voice_matched_result,
                input_text=teacher_result.get("wav_path", ""),
                input_mode=voice_match_input_mode,
                route_reason=voice_match_reason,
                default_voice=active_voice,
                voice_clone_enabled=voice_match_requested,
            )
            voice_matched_route["tts_model"] = voice_matched_result.get("model", self.cfg.voice_conversion_model)
            voice_matched_route["voice_clone_provider"] = voice_matched_result.get("voice_clone_provider") or self.cfg.voice_conversion_provider
            voice_matched_route["route_role"] = "voice_identity_transfer"
            gap_summary = self._build_gap_summary(
                teacher_route=teacher_route,
                voice_matched_route=voice_matched_route,
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
            primary_route = voice_matched_route if recommended_main_output == "voice_matched" else teacher_route
            tts = {
                "wav_path": primary_route["wav_path"],
                "audio_url": primary_route["audio_url"],
                "expires_at": primary_route["expires_at"],
                "tts_model": primary_route["tts_model"],
                "tts_voice": primary_route["tts_voice"],
                "latency_ms": round(float(teacher_route["latency_ms"]) + float(voice_matched_route["latency_ms"]), 2),
                "error": primary_route["error"],
                "voice_clone_enabled": voice_matched_route["voice_clone_enabled"],
                "voice_clone_provider": voice_matched_route["voice_clone_provider"],
                "speaker_similarity_note": primary_route["speaker_similarity_note"],
                "clone_mode": primary_route["clone_mode"],
                "fallback_reason": primary_route["fallback_reason"],
                "speaker_similarity_priority": primary_route["speaker_similarity_priority"],
                "tts_fluency_mode": primary_route["tts_fluency_mode"],
                "tts_style_instructions": primary_route["tts_style_instructions"],
                "instruction_mode_active": primary_route["instruction_mode_active"],
                "tts_input_text": teacher_route["input_text"],
                "tts_input_mode": teacher_route["input_mode"],
                "audio_meta": primary_route["audio_meta"],
                "baseline_wav_path": teacher_route["wav_path"],
                "baseline_audio_url": teacher_route["audio_url"],
                "baseline_tts_model": teacher_route["tts_model"],
                "baseline_tts_voice": teacher_route["tts_voice"],
                "baseline_error": teacher_route["error"],
                "baseline_tts_input_text": teacher_route["input_text"],
                "baseline_tts_input_mode": teacher_route["input_mode"],
                "baseline_audio_meta": teacher_route["audio_meta"],
                "baseline": teacher_route,
                "clone": voice_matched_route,
                "gap_summary": gap_summary,
                "gold_teacher": teacher_route,
                "voice_matched": voice_matched_route,
                "legacy_text_clone": None,
                "recommended_main_output": recommended_main_output,
                "voice_match_summary": voice_match_summary,
                "timbre_ref_audio": str(speaker_ref_audio) if speaker_ref_audio else "",
                "prosody_ref_audio": "",
                "prosody_guidance_mode": "",
            }

        if rewrite is None:
            rewrite = self._finish_display_rewrite(
                rewrite_future,
                rewrite_executor,
                translation_notes=translation_notes,
            )

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
