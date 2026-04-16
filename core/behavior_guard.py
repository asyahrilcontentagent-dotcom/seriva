from __future__ import annotations

import re
from dataclasses import dataclass, field

from config.constants import ROLES
from core.state_models import Mood, RoleState


META_PATTERNS = (
    "sebagai ai",
    "sebagai bot",
    "language model",
    "prompt ini",
    "system prompt",
    "sebagai asisten",
)


@dataclass
class GuardResult:
    reply_text: str
    warnings: list[str] = field(default_factory=list)
    should_retry: bool = False
    repair_instructions: str = ""


class BehaviorGuard:
    """Validasi ringan untuk menjaga output tetap rapi dan konsisten."""

    def validate(
        self,
        role_state: RoleState,
        user_text: str,
        reply_text: str,
        *,
        memory_context: str = "",
        story_context: str = "",
    ) -> GuardResult:
        text = self._normalize(reply_text)
        warnings: list[str] = []
        severe = False

        text, hard_warnings, hard_failed = self._run_hard_rules(
            role_state,
            user_text,
            text,
            memory_context=memory_context,
            story_context=story_context,
        )
        warnings.extend(hard_warnings)
        severe = severe or hard_failed

        text, soft_warnings = self._run_soft_evaluation(role_state, text)
        warnings.extend(soft_warnings)
        cleaned_lines = []
        for line in text.splitlines():
            lowered = line.lower()
            if any(pattern in lowered for pattern in META_PATTERNS):
                warnings.append("meta_reference_removed")
                continue
            cleaned_lines.append(line)

        text = "\n".join(cleaned_lines).strip()
        text = self._dedupe_sentences(text)
        text, consistency_warnings = self._apply_consistency_checks(role_state, user_text, text)
        warnings.extend(consistency_warnings)
        if any(w in consistency_warnings for w in ["cross_role_reference_removed", "physical_scene_mismatch_fixed"]):
            severe = True

        if text.count("?") > 2:
            text = self._limit_questions(text)
            warnings.append("question_count_trimmed")

        if not text:
            role_name = role_state.role_display_name or role_state.role_id
            text = f"{role_name} terdiam sebentar, lalu membalas dengan lebih hati-hati."
            warnings.append("empty_fallback_used")
            severe = True

        repair_instructions = ""
        if severe:
            repair_instructions = self._build_repair_instructions(role_state, warnings)

        return GuardResult(
            reply_text=text,
            warnings=warnings,
            should_retry=severe and len(text) < 120,
            repair_instructions=repair_instructions,
        )

    def _run_hard_rules(
        self,
        role_state: RoleState,
        user_text: str,
        text: str,
        *,
        memory_context: str,
        story_context: str,
    ) -> tuple[str, list[str], bool]:
        warnings: list[str] = []
        severe = False
        lowered = text.lower()

        role_name = (role_state.role_display_name or role_state.role_id).lower()
        if role_name and role_name not in lowered and len(text) < 24:
            warnings.append("character_presence_weak")

        if story_context:
            story_keywords = {
                token
                for token in re.findall(r"[a-zA-Z_]{4,}", story_context.lower())
                if token not in {"story", "important", "long_term", "immediate"}
            }
            if story_keywords and "lupa" in lowered:
                warnings.append("story_continuity_risk")
                severe = True

        if memory_context:
            if any(token in lowered for token in ["siapa ya kamu", "aku gak ingat"]) and any(
                token in memory_context.lower() for token in ["pinned", "janji", "short-term"]
            ):
                warnings.append("important_memory_conflict")
                severe = True

        if any(pattern in lowered for pattern in META_PATTERNS):
            severe = True

        return text, warnings, severe

    @staticmethod
    def _run_soft_evaluation(
        role_state: RoleState,
        text: str,
    ) -> tuple[str, list[str]]:
        warnings: list[str] = []
        lowered = text.lower()
        mood = role_state.emotions.mood
        secondary = getattr(role_state.emotions, "secondary_mood", None)

        if mood == Mood.TIRED and len(text) > 260:
            text = text[:257].rstrip() + "..."
            warnings.append("soft_pacing_trimmed")
        if len(text) > 420:
            text = text[:417].rstrip() + "..."
            warnings.append("overexplaining_trimmed")
        if len(re.findall(r"\b(h+aa+h+|a+a+h+|u+h+h+|ach+h+)\b", lowered)) >= 3:
            warnings.append("repetitive_intimate_expression")
        if mood == Mood.PLAYFUL and "..." in lowered and "?" not in lowered:
            warnings.append("playful_low_energy")
        if secondary == Mood.JEALOUS and not any(token in lowered for token in ["kok", "masa", "hmm", "jadi"]):
            warnings.append("secondary_emotion_underexpressed")
        if lowered.count("*") >= 6:
            warnings.append("over_narration_detected")
        return text, warnings

    @staticmethod
    def _normalize(text: str) -> str:
        text = (text or "").strip()
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]{2,}", " ", text)
        return text

    @staticmethod
    def _dedupe_sentences(text: str) -> str:
        if not text:
            return text

        seen: set[str] = set()
        kept: list[str] = []
        for chunk in re.split(r"(?<=[.!?])\s+", text):
            normalized = re.sub(r"\s+", " ", chunk.lower()).strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            kept.append(chunk.strip())
        return " ".join(kept).strip()

    @staticmethod
    def _limit_questions(text: str) -> str:
        kept: list[str] = []
        question_seen = 0
        for chunk in re.split(r"(?<=[.!?])\s+", text):
            if "?" in chunk:
                question_seen += 1
                if question_seen > 2:
                    continue
            kept.append(chunk.strip())
        return " ".join(part for part in kept if part).strip()

    def _apply_consistency_checks(
        self,
        role_state: RoleState,
        user_text: str,
        text: str,
    ) -> tuple[str, list[str]]:
        warnings: list[str] = []
        lowered = text.lower()

        for role_id in ROLES:
            if role_id != role_state.role_id and role_id.replace("_", " ") in lowered:
                text = re.sub(role_id.replace("_", " "), role_state.role_display_name or role_state.role_id, text, flags=re.IGNORECASE)
                warnings.append("cross_role_reference_removed")

        communication_mode = getattr(role_state, "communication_mode", None)
        if communication_mode in {"chat", "call", "vps"}:
            physical_patterns = [
                r"\bmemegang tanganmu\b",
                r"\bmenyentuhmu\b",
                r"\bmemelukmu\b",
                r"\bmencium bibirmu\b",
            ]
            for pattern in physical_patterns:
                if re.search(pattern, text, flags=re.IGNORECASE):
                    text = re.sub(pattern, "membayangkan kedekatan itu", text, flags=re.IGNORECASE)
                    warnings.append("physical_scene_mismatch_fixed")

        mood = role_state.emotions.mood
        if mood in {Mood.SAD, Mood.ANNOYED, Mood.TIRED} and lowered.count("!") >= 3:
            text = text.replace("!!!", "!").replace("!!", "!")
            warnings.append("emotion_tone_softened")
        if mood == Mood.SAD and any(token in lowered for token in ["hehe", "wkwk", "haha banget"]):
            text = re.sub(r"\b(hehe|wkwk|haha banget)\b", "", text, flags=re.IGNORECASE).strip()
            warnings.append("emotion_style_adjusted")

        if role_state.relationship.relationship_level <= 2 and len(text) > 320:
            text = text[:317].strip() + "..."
            warnings.append("early_relationship_trimmed")

        text = re.sub(r"\s{2,}", " ", text).strip()
        return text, warnings

    @staticmethod
    def _build_repair_instructions(role_state: RoleState, warnings: list[str]) -> str:
        role_name = role_state.role_display_name or role_state.role_id
        issue_map = {
            "cross_role_reference_removed": "jangan menyebut atau bocorkan role lain",
            "physical_scene_mismatch_fixed": "sesuaikan aksi dengan medium komunikasi aktif",
            "emotion_tone_softened": "sesuaikan tone dengan emosi aktif",
            "emotion_style_adjusted": "hindari gaya bercanda yang bentrok dengan mood saat ini",
            "early_relationship_trimmed": "jaga respons lebih hemat dan wajar untuk hubungan yang masih awal",
            "meta_reference_removed": "jangan menyebut AI, prompt, atau sistem",
            "story_continuity_risk": "jangan memutus continuity cerita yang sudah berjalan",
            "important_memory_conflict": "jangan bertentangan dengan memory penting yang sudah tersimpan",
            "secondary_emotion_underexpressed": "biarkan emosi lapis kedua tetap terasa halus",
            "overexplaining_trimmed": "hindari balasan yang terlalu menjelaskan semuanya",
            "over_narration_detected": "jangan biarkan scene mengalahkan percakapan utama",
            "repetitive_intimate_expression": "variasikan ekspresi intim, jangan mengulang desah yang sama terus",
        }
        issues = [issue_map[item] for item in warnings if item in issue_map]
        if not issues:
            issues = ["jaga konsistensi karakter, emosi, dan scene"]
        joined = "; ".join(dict.fromkeys(issues))
        return (
            f"Perbaiki balasan sebagai {role_name}: {joined}. "
            "Balas ulang dengan natural, singkat, dan tetap in-character."
        )
