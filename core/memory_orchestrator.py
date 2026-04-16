from __future__ import annotations

from dataclasses import dataclass, field

from memory.message_history import MessageHistoryStore
from memory.story_memory import StoryMemoryStore


@dataclass(frozen=True)
class ContextBudget:
    message_memory_chars: int = 620
    story_memory_chars: int = 420
    scene_chars: int = 180
    emotion_chars: int = 260


@dataclass
class StructuredContext:
    mode: str
    priority_reason: str
    budget: ContextBudget
    message_memory: str
    story_memory: str
    scene_context: str
    emotion_context: str
    metadata: dict = field(default_factory=dict)

    def to_prompt_block(self) -> str:
        return (
            "STRUCTURED CONTEXT PIPELINE:\n"
            "- Prioritas konteks: current message -> emotional state -> recent memory -> long-term memory -> scene/story\n"
            f"- Mode prioritas: {self.mode}\n"
            f"- Alasan prioritas: {self.priority_reason}\n"
            f"- Budget message_memory: {self.budget.message_memory_chars} chars\n"
            f"- Budget story_memory: {self.budget.story_memory_chars} chars\n"
            f"- Budget scene: {self.budget.scene_chars} chars\n"
            f"- Budget emotion: {self.budget.emotion_chars} chars\n\n"
            "MESSAGE MEMORY:\n"
            f"{self.message_memory or '-'}\n\n"
            "STORY MEMORY:\n"
            f"{self.story_memory or '-'}\n\n"
            "SCENE FOCUS:\n"
            f"{self.scene_context or '-'}\n\n"
            "EMOTION FOCUS:\n"
            f"{self.emotion_context or '-'}"
        )


class MemoryOrchestrator:
    """Satukan message memory, story memory, scene, dan emosi dalam satu pipeline."""

    def __init__(
        self,
        message_history: MessageHistoryStore,
        story_memory: StoryMemoryStore,
        *,
        default_budget: ContextBudget | None = None,
    ) -> None:
        self.message_history = message_history
        self.story_memory = story_memory
        self.default_budget = default_budget or ContextBudget()

    def build_context(
        self,
        *,
        user_id: str,
        role_id: str,
        user_message: str,
        role_state,
    ) -> StructuredContext:
        mode, reason = self._choose_mode(user_message=user_message, role_state=role_state)
        budget = self._budget_for_mode(mode)
        message_packet = self.message_history.get_memory_packet(
            user_id,
            role_id,
            query_text=user_message,
            top_k=6 if mode != "story_dominant" else 4,
            min_score=18.0 if mode == "message_dominant" else 22.0,
        )
        story_tiers = self.story_memory.get_story_tiers(user_id, role_id)

        message_memory = self._trim(
            self._render_message_memory(message_packet, role_id),
            budget.message_memory_chars,
        )
        story_memory = self._trim(
            self._render_story_memory(story_tiers),
            budget.story_memory_chars,
        )
        scene_context = self._trim(
            self._render_scene(role_state),
            budget.scene_chars,
        )
        emotion_context = self._trim(
            self._render_emotion(role_state),
            budget.emotion_chars,
        )

        return StructuredContext(
            mode=mode,
            priority_reason=reason,
            budget=budget,
            message_memory=message_memory,
            story_memory=story_memory,
            scene_context=scene_context,
            emotion_context=emotion_context,
            metadata={
                "message_selected": len(message_packet["items"]),
                "pinned_selected": len(message_packet.get("pinned", [])),
                "story_arc": self.story_memory.get_or_create(user_id, role_id).current_arc,
            },
        )

    def _choose_mode(self, *, user_message: str, role_state) -> tuple[str, str]:
        lowered = (user_message or "").lower()
        story_pressure = 0
        message_pressure = 0

        if any(token in lowered for token in ["tadi", "barusan", "ingat", "kok kamu bilang", "kenapa tadi"]):
            message_pressure += 3
        if any(token in lowered for token in ["janji", "hubungan", "lanjut", "masih", "kemarin", "besok"]):
            story_pressure += 2
        if any(token in lowered for token in ["maaf", "marah", "sedih", "takut", "kecewa"]):
            story_pressure += 2
        if "?" in lowered:
            message_pressure += 1

        scene_priority = getattr(role_state.scene, "scene_priority", 0)
        if scene_priority >= 6:
            story_pressure += 1
        if getattr(role_state.relationship, "relationship_level", 0) <= 3:
            message_pressure += 1

        if story_pressure >= message_pressure + 2:
            return "story_dominant", "Percakapan menuntut kontinuitas cerita dan emosi jangka menengah."
        if message_pressure >= story_pressure + 2:
            return "message_dominant", "Pesan user lebih bergantung pada detail percakapan terbaru."
        return "balanced", "Butuh campuran memory terbaru dan continuity cerita."

    def _budget_for_mode(self, mode: str) -> ContextBudget:
        if mode == "story_dominant":
            return ContextBudget(
                message_memory_chars=470,
                story_memory_chars=620,
                scene_chars=160,
                emotion_chars=300,
            )
        if mode == "message_dominant":
            return ContextBudget(
                message_memory_chars=760,
                story_memory_chars=320,
                scene_chars=150,
                emotion_chars=280,
            )
        return self.default_budget

    @staticmethod
    def _render_message_memory(packet: dict, role_id: str) -> str:
        parts: list[str] = []
        labels = [
            ("short_term", "short-term"),
            ("key_events", "key-events"),
            ("long_term", "long-term"),
        ]
        for key, label in labels:
            items = packet.get(key, [])
            if not items:
                continue
            rendered = []
            for item in sorted(items, key=lambda entry: entry.snippet.timestamp):
                speaker = "Mas" if item.snippet.from_who == "user" else role_id
                rendered.append(f"{speaker}: {item.snippet.content[:90].strip()}")
            parts.append(f"{label}= " + " | ".join(rendered[:2]))
        if packet.get("pinned"):
            pins = []
            for item in packet["pinned"][:2]:
                speaker = "Mas" if item.snippet.from_who == "user" else role_id
                pins.append(f"{speaker}: {item.snippet.content[:90].strip()}")
            parts.append("pinned= " + " | ".join(pins))
        return "\n".join(parts) if parts else "-"

    @staticmethod
    def _render_story_memory(story_tiers: dict) -> str:
        return (
            f"immediate={story_tiers.get('immediate', '-')}\n"
            f"important={story_tiers.get('important', '-')}\n"
            f"long_term={story_tiers.get('long_term', '-')}"
        )

    @staticmethod
    def _render_scene(role_state) -> str:
        scene = role_state.scene
        bits = [
            f"lokasi={scene.location or '-'}",
            f"aktivitas={scene.activity or '-'}",
            f"jarak={scene.physical_distance or '-'}",
            f"sentuhan={scene.last_touch or '-'}",
        ]
        return "; ".join(bits)

    @staticmethod
    def _render_emotion(role_state) -> str:
        emotions = role_state.emotions
        primary = getattr(emotions, "mood", None)
        secondary = getattr(emotions, "secondary_mood", None)
        hidden = getattr(emotions, "hidden_mood", None)
        drift = getattr(emotions, "emotional_drift", 0.0)
        return (
            f"primary={primary.value if primary else '-'}; "
            f"secondary={secondary.value if secondary else '-'}; "
            f"hidden={hidden.value if hidden else '-'}; "
            f"love={emotions.love}; comfort={emotions.comfort}; longing={emotions.longing}; drift={drift:.2f}"
        )

    @staticmethod
    def _trim(text: str, limit: int) -> str:
        compact = " ".join((text or "-").split())
        if len(compact) <= limit:
            return compact
        return compact[: limit - 3] + "..."
