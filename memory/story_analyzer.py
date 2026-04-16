from __future__ import annotations

from dataclasses import dataclass, field

from memory.story_memory import StoryBeat, StoryMemoryStore


@dataclass
class StorySignal:
    name: str
    confidence: float
    detail: str


@dataclass
class StoryAnalysisResult:
    triggered_beats: list[StorySignal] = field(default_factory=list)
    vibe: str = "natural"
    emotional_spike: bool = False


class StoryAnalyzer:
    """Analisis ringan untuk mendeteksi momen cerita otomatis."""

    MIN_CONFIDENCE = 0.62

    def __init__(self, story_memory: StoryMemoryStore) -> None:
        self.story_memory = story_memory

    def analyze_and_apply(
        self,
        *,
        user_id: str,
        role_id: str,
        user_text: str,
        reply_text: str,
    ) -> StoryAnalysisResult:
        lowered = f"{user_text} {reply_text}".lower()
        signals = self._detect_signals(lowered, user_text=user_text, reply_text=reply_text)
        result = StoryAnalysisResult(
            triggered_beats=[],
            vibe=self._detect_vibe(lowered),
            emotional_spike=any(signal.name == "emotional_spike" for signal in signals),
        )

        self.story_memory.update_vibe(user_id, role_id, result.vibe)

        for signal in signals:
            if signal.confidence < self.MIN_CONFIDENCE:
                continue
            beat = self._map_signal_to_beat(signal.name)
            if beat and self.story_memory.add_story_beat(user_id, role_id, beat, signal.detail):
                result.triggered_beats.append(signal)

        return result

    def _detect_signals(self, lowered: str, *, user_text: str, reply_text: str) -> list[StorySignal]:
        signals: list[StorySignal] = []

        confession_hits = sum(token in lowered for token in ["aku sayang", "aku cinta", "sayang kamu", "cinta kamu"])
        if confession_hits:
            signals.append(
                StorySignal(
                    name="confession",
                    confidence=min(0.95, 0.58 + (0.18 * confession_hits)),
                    detail=f"Confession terdeteksi dari: {user_text[:80]}",
                )
            )

        fight_hits = sum(token in lowered for token in ["marah", "kesal", "jangan ganggu", "capek sama", "kecewa"])
        if fight_hits:
            signals.append(
                StorySignal(
                    name="fight",
                    confidence=min(0.9, 0.52 + (0.14 * fight_hits)),
                    detail=f"Konflik terdeteksi dari: {user_text[:80]}",
                )
            )

        promise_hits = sum(token in lowered for token in ["janji", "aku bakal", "aku akan", "nanti aku"])
        if promise_hits:
            signals.append(
                StorySignal(
                    name="promise",
                    confidence=min(0.88, 0.50 + (0.12 * promise_hits)),
                    detail=f"Janji terdeteksi dari: {reply_text[:80] or user_text[:80]}",
                )
            )

        spike_hits = sum(token in lowered for token in ["sedih", "takut", "kangen banget", "lega", "terharu", "gemetar"])
        if spike_hits >= 2:
            signals.append(
                StorySignal(
                    name="emotional_spike",
                    confidence=min(0.84, 0.55 + (0.1 * spike_hits)),
                    detail=f"Lonjakan emosi dari: {user_text[:80]}",
                )
            )

        return signals

    @staticmethod
    def _detect_vibe(lowered: str) -> str:
        vibe_scores = {
            "warm": ["tenang", "hangat", "lega", "nyaman", "pelan"],
            "playful": ["becanda", "iseng", "genit", "jahil", "hehe"],
            "tense": ["marah", "diam", "tegang", "kesal", "dingin"],
            "sad": ["sedih", "kecewa", "capek", "takut", "nangis"],
            "romantic": ["sayang", "rindu", "peluk", "cinta", "kangen"],
        }
        scores = {
            vibe: sum(token in lowered for token in keywords)
            for vibe, keywords in vibe_scores.items()
        }
        best_vibe = max(scores, key=scores.get)
        return best_vibe if scores[best_vibe] > 0 else "natural"

    @staticmethod
    def _map_signal_to_beat(signal_name: str) -> StoryBeat | None:
        mapping = {
            "confession": StoryBeat.CONFESSION,
            "fight": StoryBeat.FIGHT,
            "promise": StoryBeat.PROMISE,
        }
        return mapping.get(signal_name)
