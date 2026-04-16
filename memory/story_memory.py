"""Story-aware memory untuk menjaga alur cerita tetap konsisten."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from threading import RLock
from typing import Dict, List


class StoryBeat(Enum):
    FIRST_MEET = "first_meet"
    FIRST_FLIRT = "first_flirt"
    FIRST_KISS = "first_kiss"
    FIRST_INTIMATE = "first_intimate"
    CONFESSION = "confession"
    FIGHT = "fight"
    MAKEOUT = "makeout"
    CLIMAX = "climax"
    AFTERCARE = "aftercare"
    PROMISE = "promise"
    JEALOUSY = "jealousy"
    FAREWELL = "farewell"


@dataclass
class StoryContext:
    user_id: str
    role_id: str
    story_beats: List[StoryBeat] = field(default_factory=list)
    current_arc: str = "introduction"
    pending_actions: List[str] = field(default_factory=list)
    story_location: str = ""
    story_vibe: str = "natural"
    last_scene_summary: str = ""
    last_scene_timestamp: float = 0.0
    plot_milestones: List[str] = field(default_factory=list)
    promises: List[str] = field(default_factory=list)
    nicknames_used: List[str] = field(default_factory=list)


class StoryMemoryStore:
    """Menyimpan konteks cerita per user-role."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._data: Dict[tuple[str, str], StoryContext] = {}

    def get_or_create(self, user_id: str, role_id: str) -> StoryContext:
        key = (user_id, role_id)
        with self._lock:
            if key not in self._data:
                self._data[key] = StoryContext(user_id=user_id, role_id=role_id)
            return self._data[key]

    def add_story_beat(self, user_id: str, role_id: str, beat: StoryBeat, context: str = "") -> bool:
        story = self.get_or_create(user_id, role_id)
        with self._lock:
            if beat in story.story_beats:
                return False

            story.story_beats.append(beat)
            timestamp = time.strftime("%H:%M")
            detail = context[:100] if context else "Terjadi momen penting"
            story.plot_milestones.append(f"[{timestamp}] {beat.value}: {detail}")

            if beat in {StoryBeat.FIRST_KISS, StoryBeat.FIRST_INTIMATE, StoryBeat.MAKEOUT}:
                story.current_arc = "intimacy"
            elif beat == StoryBeat.CLIMAX:
                story.current_arc = "climax"
            elif beat in {StoryBeat.FIGHT, StoryBeat.JEALOUSY}:
                story.current_arc = "tension"
            elif beat == StoryBeat.AFTERCARE:
                story.current_arc = "resolution"

            self._prune_story_context(story)
            return True

    def update_scene_summary(self, user_id: str, role_id: str, summary: str) -> None:
        story = self.get_or_create(user_id, role_id)
        with self._lock:
            story.last_scene_summary = summary[:500]
            story.last_scene_timestamp = time.time()

    def update_location(self, user_id: str, role_id: str, location: str) -> None:
        story = self.get_or_create(user_id, role_id)
        with self._lock:
            story.story_location = location

    def update_vibe(self, user_id: str, role_id: str, vibe: str) -> None:
        valid_vibes = {"romantic", "playful", "tense", "sad", "natural", "warm"}
        if vibe not in valid_vibes:
            return
        story = self.get_or_create(user_id, role_id)
        with self._lock:
            story.story_vibe = vibe

    def add_promise(self, user_id: str, role_id: str, promise: str) -> None:
        story = self.get_or_create(user_id, role_id)
        with self._lock:
            if promise not in story.promises:
                story.promises.append(promise)
                self._prune_story_context(story)

    def add_pending_action(self, user_id: str, role_id: str, action: str) -> None:
        story = self.get_or_create(user_id, role_id)
        with self._lock:
            if action not in story.pending_actions:
                story.pending_actions.append(action)

    def clear_pending_actions(self, user_id: str, role_id: str) -> None:
        story = self.get_or_create(user_id, role_id)
        with self._lock:
            story.pending_actions.clear()

    def add_nickname(self, user_id: str, role_id: str, nickname: str) -> None:
        story = self.get_or_create(user_id, role_id)
        with self._lock:
            if nickname not in story.nicknames_used:
                story.nicknames_used.append(nickname)
                self._prune_story_context(story)

    def get_ranked_milestones(self, user_id: str, role_id: str, limit: int = 5) -> List[str]:
        story = self.get_or_create(user_id, role_id)
        with self._lock:
            ranked = sorted(story.plot_milestones, key=self._score_milestone, reverse=True)
            return ranked[:limit]

    def get_story_summary(self, user_id: str, role_id: str) -> str:
        story = self.get_or_create(user_id, role_id)
        with self._lock:
            beats = ", ".join(beat.value for beat in story.story_beats[-3:]) or "belum ada beat penting"
            promises = ", ".join(story.promises[-2:]) or "tidak ada janji aktif"
            return (
                f"arc={story.current_arc}; vibe={story.story_vibe}; "
                f"lokasi={story.story_location or 'belum menonjol'}; beat={beats}; janji={promises}"
            )

    def get_story_tiers(self, user_id: str, role_id: str) -> dict:
        story = self.get_or_create(user_id, role_id)
        ranked = self.get_ranked_milestones(user_id, role_id, limit=6)
        with self._lock:
            immediate = story.last_scene_summary[:180] if story.last_scene_summary else "-"
            important = " | ".join(ranked[:3]) if ranked else "-"
            long_term = (
                f"arc={story.current_arc}; vibe={story.story_vibe}; "
                f"janji={', '.join(story.promises[-2:]) or '-'}; "
                f"lokasi={story.story_location or '-'}"
            )
            return {
                "immediate": immediate,
                "important": important,
                "long_term": long_term,
            }

    def get_story_prompt(self, user_id: str, role_id: str) -> str:
        story = self.get_or_create(user_id, role_id)
        ranked_milestones = self.get_ranked_milestones(user_id, role_id, limit=5)

        if not story.story_beats and not story.plot_milestones:
            return (
                "ALUR CERITA: Ini masih tahap awal. Belum ada memory penting yang wajib dirujuk."
            )

        pending_str = ""
        if story.pending_actions:
            pending_str = "\n- Aksi yang belum selesai: " + ", ".join(story.pending_actions)

        promise_str = ""
        if story.promises:
            promise_str = "\n- Janji yang masih aktif: " + ", ".join(story.promises[-3:])

        nickname_str = ""
        if story.nicknames_used:
            nickname_str = "\n- Nama panggilan yang pernah dipakai: " + ", ".join(story.nicknames_used[-4:])

        milestone_lines = "\n".join(f"  - {item}" for item in ranked_milestones) or "  - Belum ada"
        return (
            "KONTEKS CERITA YANG WAJIB DIJAGA:\n"
            f"- Arc saat ini: {story.current_arc}\n"
            f"- Suasana utama: {story.story_vibe}\n"
            f"- Lokasi cerita: {story.story_location or 'masih mengikuti lokasi sebelumnya'}\n"
            f"- Adegan terakhir: {story.last_scene_summary or 'adegan baru dimulai'}\n"
            "- Momen penting relevan:\n"
            f"{milestone_lines}"
            f"{pending_str}"
            f"{promise_str}"
            f"{nickname_str}\n\n"
            "ATURAN KONTINUITAS:\n"
            "- Jangan restart hubungan atau melupakan progres yang sudah terjadi.\n"
            "- Referensikan memory lama hanya bila relevan dengan pesan terbaru.\n"
            "- Kembangkan adegan ke arah baru, jangan mengulang beat yang sama terus.\n"
            "- Jaga arc cerita tetap konsisten dengan suasana saat ini."
        )

    def reset_story(self, user_id: str, role_id: str) -> None:
        key = (user_id, role_id)
        with self._lock:
            self._data.pop(key, None)

    def get_summary_for_admin(self, user_id: str, role_id: str) -> dict:
        story = self.get_or_create(user_id, role_id)
        return {
            "user_id": user_id,
            "role_id": role_id,
            "current_arc": story.current_arc,
            "story_vibe": story.story_vibe,
            "story_location": story.story_location,
            "total_beats": len(story.story_beats),
            "total_milestones": len(story.plot_milestones),
            "total_promises": len(story.promises),
            "last_scene": story.last_scene_summary[:100] if story.last_scene_summary else None,
        }

    @staticmethod
    def _score_milestone(text: str) -> float:
        lowered = text.lower()
        score = len(text) / 20
        if "confession" in lowered or "promise" in lowered:
            score += 25
        if "first_" in lowered:
            score += 18
        if "fight" in lowered or "farewell" in lowered:
            score += 14
        return score

    @staticmethod
    def _prune_story_context(story: StoryContext, max_milestones: int = 20) -> None:
        if len(story.plot_milestones) > max_milestones:
            story.plot_milestones = story.plot_milestones[-max_milestones:]
        if len(story.promises) > 6:
            story.promises = story.promises[-6:]
        if len(story.nicknames_used) > 8:
            story.nicknames_used = story.nicknames_used[-8:]
