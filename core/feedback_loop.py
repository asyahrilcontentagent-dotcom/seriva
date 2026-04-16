from __future__ import annotations

import logging
from dataclasses import dataclass, field


logger = logging.getLogger(__name__)


@dataclass
class OutputEvaluation:
    consistent: bool
    relevant: bool
    notes: list[str] = field(default_factory=list)


class FeedbackLoop:
    """Evaluasi ringan setelah output untuk update state dan debugging."""

    def evaluate(
        self,
        *,
        role_state,
        user_text: str,
        reply_text: str,
        structured_context=None,
    ) -> OutputEvaluation:
        notes: list[str] = []
        lowered_reply = (reply_text or "").lower()
        lowered_user = (user_text or "").lower()

        consistent = True
        relevant = True

        if not reply_text.strip():
            consistent = False
            relevant = False
            notes.append("empty_reply")

        if lowered_user and not any(token in lowered_reply for token in lowered_user.split()[:2]) and len(reply_text) < 20:
            relevant = False
            notes.append("thin_relevance")

        if getattr(role_state, "last_guard_warnings", None):
            consistent = False
            notes.append("guard_warning_present")

        if structured_context and structured_context.mode == "story_dominant" and len(reply_text) < 30:
            notes.append("story_reply_too_short")

        return OutputEvaluation(consistent=consistent, relevant=relevant, notes=notes)

    def apply(
        self,
        *,
        role_state,
        evaluation: OutputEvaluation,
    ) -> None:
        emotions = role_state.emotions
        if evaluation.consistent and evaluation.relevant:
            emotions.comfort = min(100, emotions.comfort + 1)
        else:
            emotions.comfort = max(0, emotions.comfort - 1)
        setattr(role_state, "last_output_evaluation", evaluation.notes[:6])
        emotions.clamp()

    def log(
        self,
        *,
        user_id: str,
        role_id: str,
        evaluation: OutputEvaluation,
    ) -> None:
        logger.info(
            "feedback_loop user=%s role=%s consistent=%s relevant=%s notes=%s",
            user_id,
            role_id,
            evaluation.consistent,
            evaluation.relevant,
            ",".join(evaluation.notes) or "-",
        )
