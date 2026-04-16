from __future__ import annotations

from typing import Any


def build_debug_trace(
    *,
    role_state,
    structured_context=None,
    messages: list[dict[str, Any]] | None = None,
) -> str:
    emotions = role_state.emotions
    active_rules: list[str] = [
        f"mood={emotions.mood.value}",
        f"secondary={getattr(emotions, 'secondary_mood', emotions.mood).value}",
        f"hidden={getattr(emotions, 'hidden_mood', emotions.mood).value}",
        f"relationship={role_state.relationship.relationship_level}",
        f"phase={role_state.intimacy_phase.value}",
        f"length_bias={getattr(role_state, 'response_length_bias', 'balanced')}",
        f"initiative={getattr(role_state, 'social_initiative_level', 0)}",
        f"energy={getattr(role_state, 'daily_energy', 0)}",
        f"time={getattr(role_state, 'last_temporal_label', '-')}",
    ]

    if getattr(role_state, "last_guard_warnings", None):
        active_rules.append("guard=" + ",".join(role_state.last_guard_warnings[:4]))
    if getattr(role_state, "last_output_evaluation", None):
        active_rules.append("feedback=" + ",".join(role_state.last_output_evaluation[:4]))

    final_prompt = ""
    if messages:
        system_parts = [str(msg.get("content", "")) for msg in messages if msg.get("role") == "system"]
        final_prompt = "\n\n".join(system_parts[:4])[:4000]

    lines = [
        "[DEBUG_TRACE]",
        (
            "emotion_state="
            f"love:{emotions.love}, longing:{emotions.longing}, comfort:{emotions.comfort}, jealousy:{emotions.jealousy}, drift:{getattr(emotions, 'emotional_drift', 0.0):.2f}"
        ),
        f"intimacy_foundation=depth:{getattr(role_state, 'emotional_depth_score', 0)}, trust:{getattr(role_state, 'trust_score', 0)}, brake:{getattr(role_state, 'intimacy_brake_active', False)}",
        f"relationship_profile=attachment:{getattr(role_state, 'attachment_style', '-')}, love_language:{getattr(role_state, 'dominant_love_language', '-')}, pacing:{getattr(role_state, 'intimacy_pacing', '-')}",
        f"intimate_expression=style:{getattr(role_state, 'intimate_expression_style', '-')}, restraint:{getattr(role_state, 'moan_restraint', 0)}, breathiness:{getattr(role_state, 'breathiness_level', 0)}",
        f"memory_used={getattr(role_state, 'last_used_memory_summary', '-') or '-'}",
        f"story_used={getattr(role_state, 'last_used_story_summary', '-') or '-'}",
        f"habits={', '.join(getattr(role_state, 'personality_habits', [])[:3]) or '-'}",
        f"topics={', '.join(getattr(role_state, 'favorite_topics', [])[:3]) or '-'}",
        f"closure={getattr(role_state, 'session_closure_summary', '-') or '-'}",
        "active_rules=" + " | ".join(active_rules),
    ]

    if structured_context:
        lines.append(
            "context_mode="
            f"{structured_context.mode}; reason={structured_context.priority_reason}; metadata={structured_context.metadata}"
        )
    if final_prompt:
        lines.append("final_prompt=" + final_prompt)

    return "\n".join(lines)
