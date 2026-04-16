from __future__ import annotations

import re
from dataclasses import dataclass, field

from core.state_models import RoleState


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


class BehaviorGuard:
    """Validasi ringan untuk menjaga output tetap rapi dan konsisten."""

    def validate(
        self,
        role_state: RoleState,
        user_text: str,
        reply_text: str,
    ) -> GuardResult:
        text = self._normalize(reply_text)
        warnings: list[str] = []

        cleaned_lines = []
        for line in text.splitlines():
            lowered = line.lower()
            if any(pattern in lowered for pattern in META_PATTERNS):
                warnings.append("meta_reference_removed")
                continue
            cleaned_lines.append(line)

        text = "\n".join(cleaned_lines).strip()
        text = self._dedupe_sentences(text)

        if text.count("?") > 2:
            text = self._limit_questions(text)
            warnings.append("question_count_trimmed")

        if not text:
            role_name = role_state.role_display_name or role_state.role_id
            text = f"{role_name} terdiam sebentar, lalu membalas dengan lebih hati-hati."
            warnings.append("empty_fallback_used")

        return GuardResult(reply_text=text, warnings=warnings)

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
