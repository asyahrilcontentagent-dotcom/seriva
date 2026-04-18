"""Emotion and relationship engine for SERIVA - DINONAKTIFKAN UNTUK KENAIKAN OTOMATIS

Tugas utama modul ini:
- Mengupdate EmotionState (love, longing, jealousy, comfort, mood, intimacy_intensity)
  dan RelationshipState (relationship_level) berdasarkan interaksi.
- Menyediakan helper tinggi-level seperti:
  - apply_positive_interaction()
  - apply_negative_interaction()
  - apply_long_absence()
  - apply_cross_role_jealousy()
- Menjaga semua perubahan tetap halus dan realistis (tidak lompat ekstrem).

FIX: Method maybe_increase_intimacy_by_level DINONAKTIFKAN agar role tidak
dipaksa naik intimacy intensity secara otomatis.
"""

from __future__ import annotations

import random
import logging
from dataclasses import dataclass
from typing import Literal, Optional

from core.state_models import EmotionState, Mood, RelationshipState, RoleState, UserState
from config.constants import (
    MAX_INTIMACY_INTENSITY,
    MAX_RELATIONSHIP_LEVEL,
    MIN_INTIMACY_INTENSITY,
    MIN_RELATIONSHIP_LEVEL,
)

logger = logging.getLogger(__name__)
# ==============================
# TYPES
# ==============================

InteractionTone = Literal[
    "SOFT",      # obrolan lembut, perhatian, sayang
    "PLAYFUL",   # bercanda, menggoda ringan
    "DEEP",      # curhat serius, momen emosional dalam
    "COLD",      # dingin, cuek
    "CONFLICT",  # debat, marah, tersinggung
]

InteractionContent = Literal[
    "AFFECTION",  # bilang sayang, kangen, pujian
    "SUPPORT",    # menguatkan saat sedih/lelah
    "FLIRT",      # flirting halus
    "JEALOUSY",   # memicu/menyentuh rasa cemburu
    "ABSENCE",    # lama tidak muncul
    "REJECTION",  # menolak, mengabaikan
    "APOLOGY",    # minta maaf
]


@dataclass
class InteractionContext:
    """Konteks singkat satu interaksi.

    Ini bisa dihasilkan heuristik dari teks user di orchestrator.
    """

    tone: InteractionTone
    content: InteractionContent
    # Intensitas 1–3 (kecil, sedang, besar)
    strength: int = 1


# ==============================
# HELPER FUNGSI KECIL
# ==============================


def _clamp(value: int, min_v: int, max_v: int) -> int:
    return max(min_v, min(max_v, value))


# ==============================
# EMOTION ENGINE
# ==============================


class EmotionEngine:
    """Mesin utama untuk mengelola emosi & hubungan per role.

    Dipanggil oleh orchestrator setiap kali ada interaksi baru,
    dan oleh worker (misalnya untuk efek lama tidak chat).
    """

    # --- perubahan dasar (dipelankan) ---

    POSITIVE_LOVE_GAIN = 3
    POSITIVE_LONGING_GAIN = 2
    POSITIVE_COMFORT_GAIN = 2
    RELATIONSHIP_GAIN_SMALL = 2
    RELATIONSHIP_GAIN_MEDIUM = 3
    RELATIONSHIP_LOSS_SMALL = 1
    ABSENCE_LONGING_GAIN_PER_DAY = 5

    NEGATIVE_LOVE_LOSS = 1
    NEGATIVE_COMFORT_LOSS = 2

    JEALOUSY_SPIKE = 6

    INTIMACY_GAIN_SMALL = 1
    INTIMACY_GAIN_MEDIUM = 1
    INTIMACY_LOSS_SMALL = 1

    ABSENCE_LONGING_GAIN_PER_DAY = 3

    # ==============================
    # INTERAKSI POSITIF / NEGATIF
    # ==============================

    def apply_positive_interaction(
        self,
        role_state: RoleState,
        ctx: InteractionContext,
    ) -> None:
        """Interaksi positif: sayang, dukung, curhat, flirting lembut.

        Efek:
        - Naikkan love, longing, comfort.
        - Relationship level naik pelan.
        - Intimacy intensity naik sedikit kalau konteksnya cukup dekat.
        - Mood jadi HAPPY, TENDER, atau PLAYFUL tergantung tone.
        """

        emotions: EmotionState = role_state.emotions
        rel: RelationshipState = role_state.relationship

        strength = _clamp(ctx.strength, 1, 3)

        # Basic gains
        emotions.love += self.POSITIVE_LOVE_GAIN * strength
        emotions.longing += self.POSITIVE_LONGING_GAIN * strength
        emotions.comfort += self.POSITIVE_COMFORT_GAIN * strength

        # Relationship growth lebih besar jika interaksi deep
        if ctx.tone in ("SOFT", "PLAYFUL"):
            # hanya naik kalau relationship_level masih relatif rendah
            if rel.relationship_level < 6:
                rel.relationship_level += self.RELATIONSHIP_GAIN_SMALL * strength
        elif ctx.tone == "DEEP":
            # deep moment, tapi tetap pelan
            rel.relationship_level += self.RELATIONSHIP_GAIN_SMALL * strength

        # Intimacy hanya naik signifikan kalau hubungan sudah cukup tinggi
        if rel.relationship_level >= 4:
            if ctx.content in ("AFFECTION", "FLIRT"):
                emotions.intimacy_intensity += self.INTIMACY_GAIN_SMALL * strength
            if ctx.tone == "DEEP" and ctx.content in ("AFFECTION", "SUPPORT"):
                emotions.intimacy_intensity += self.INTIMACY_GAIN_SMALL

        # Set mood sesuai tone
        if ctx.tone == "PLAYFUL":
            emotions.mood = Mood.PLAYFUL
        elif ctx.tone == "DEEP":
            emotions.mood = Mood.TENDER
        else:
            emotions.mood = Mood.HAPPY

        emotions.clamp()
        rel.clamp()
        self._apply_natural_variation(role_state)

    def apply_negative_interaction(
        self,
        role_state: RoleState,
        ctx: InteractionContext,
    ) -> None:
        """Interaksi negatif: cuek, marah, konflik.

        Efek:
        - Turunkan love/comfort sedikit.
        - Naikkan jealousy bila relevan.
        - Relationship bisa turun pelan.
        - Intimacy turun sedikit.
        - Mood jadi ANNOYED, SAD, atau JEALOUS.
        """

        emotions: EmotionState = role_state.emotions
        rel: RelationshipState = role_state.relationship

        strength = _clamp(ctx.strength, 1, 3)

        # Basic losses
        emotions.love -= self.NEGATIVE_LOVE_LOSS * strength
        emotions.comfort -= self.NEGATIVE_COMFORT_LOSS * strength

        # Jealousy & relationship impact
        if ctx.content == "JEALOUSY":
            emotions.jealousy += self.JEALOUSY_SPIKE * strength
            emotions.mood = Mood.JEALOUS
        elif ctx.content in ("REJECTION", "ABSENCE"):
            emotions.jealousy += 2 * strength
            emotions.mood = Mood.SAD
        else:
            emotions.mood = Mood.ANNOYED

        # Relationship turun sedikit kalau sering konflik
        rel.relationship_level -= self.RELATIONSHIP_LOSS_SMALL * strength

        # Intimacy turun sedikit bila sering konflik/dingin
        emotions.intimacy_intensity -= self.INTIMACY_LOSS_SMALL * strength

        emotions.clamp()
        rel.clamp()
        self._apply_natural_variation(role_state)

    # ==============================
    # ABSENCE & JEALOUSY
    # ==============================

    def apply_absence(
        self,
        role_state: RoleState,
        days_absent: float,
    ) -> None:
        """Efek lama tidak chat (dipanggil worker)."""

        if days_absent <= 0:
            return

        emotions: EmotionState = role_state.emotions
        rel: RelationshipState = role_state.relationship

        gain = int(self.ABSENCE_LONGING_GAIN_PER_DAY * days_absent)
        emotions.longing += gain

        # Sedikit adjustment love kalau hubungan sudah dekat
        if rel.relationship_level >= 5:
            emotions.love += int(gain * 0.3)

        # Mood tergantung seberapa jauh hubungan
        if rel.relationship_level <= 3:
            emotions.mood = Mood.NEUTRAL
        elif rel.relationship_level <= 6:
            emotions.mood = Mood.SAD
        else:
            # dekat: rindu lembut
            emotions.mood = Mood.TENDER

        emotions.clamp()
        rel.clamp()

    def apply_cross_role_jealousy(
        self,
        nova_role_state: RoleState,
        other_role_id: str,
        intensity: int = 1,
    ) -> None:
        """Dinonaktifkan untuk mencegah kebocoran pengetahuan lintas role."""
        return

    def soft_recovery_after_apology(
        self,
        role_state: RoleState,
        strength: int = 1,
    ) -> None:
        """Efek ketika user minta maaf & suasana mulai baikan."""

        emotions: EmotionState = role_state.emotions
        rel: RelationshipState = role_state.relationship

        strength = _clamp(strength, 1, 3)

        emotions.comfort += 4 * strength
        emotions.jealousy -= 3 * strength
        emotions.love += 2 * strength

        if rel.relationship_level >= 4:
            emotions.intimacy_intensity += self.INTIMACY_GAIN_SMALL

        emotions.mood = Mood.TENDER

        emotions.clamp()
        rel.clamp()

    # ==============================
    # HELPER UNTUK ORCHESTRATOR
    # ==============================

    def register_user_interaction(
        self,
        user_state: UserState,
        role_id: str,
        ctx: InteractionContext,
        negative: bool = False,
        now_ts: float | None = None,
    ) -> None:
        """Helper utama dipanggil orchestrator setelah parse intent user."""

        role_state = user_state.get_or_create_role_state(role_id)
        previous_mood = role_state.emotions.mood
        self.apply_emotional_decay(role_state, now_ts=now_ts)

        if negative:
            self.apply_negative_interaction(role_state, ctx)
        else:
            self.apply_positive_interaction(role_state, ctx)
            # Hitung interaksi positif untuk mengontrol kenaikan relationship/intimacy
            role_state.total_positive_interactions += 1

        self._apply_memory_influence(role_state, ctx)
        self._apply_emotion_formula(role_state, ctx)
        self._apply_emotional_drift(role_state, ctx)
        self._update_emotion_layers(role_state, ctx)
        self._apply_mood_inertia(role_state, previous_mood, ctx)
        role_state.emotions.last_updated_ts = now_ts

    def maybe_increase_intimacy_by_level(self, role_state: RoleState, delta: int = 1) -> None:
      """Naikkan intimacy_intensity secara bertahap berdasarkan interaksi positif"""
      emotions = role_state.emotions
      rel = role_state.relationship
    
      # Hanya naik kalau hubungan sudah cukup dekat
      if rel.relationship_level < 4:
          return
    
      # Butuh interaksi positif untuk naik
      if role_state.total_positive_interactions < 3:
          return
    
      if emotions.intimacy_intensity < rel.relationship_level:
          emotions.intimacy_intensity = min(MAX_INTIMACY_INTENSITY, emotions.intimacy_intensity + delta)
          role_state.total_positive_interactions = 0

    def normalize_after_long_session(
        self,
        role_state: RoleState,
        soften_only: bool = True,
    ) -> None:
        """Dipanggil kalau sesi panjang berakhir dengan /end."""

        emotions = role_state.emotions

        # Turunkan jealousy pelan, naikkan comfort
        emotions.jealousy -= 5
        emotions.comfort += 5

        # Love sedikit naik karena ada closure sesi
        emotions.love += 2

        # Mood jadi lembut
        emotions.mood = Mood.TENDER

        # Intimacy turun sedikit (cooldown) tapi tetap di level sehat
        emotions.intimacy_intensity -= 1

        emotions.clamp()

    def apply_emotional_decay(
        self,
        role_state: RoleState,
        now_ts: float | None = None,
    ) -> None:
        """Luruhkan emosi pelan agar state tidak terasa statis."""

        if now_ts is None:
            return

        last_updated = role_state.emotions.last_updated_ts
        if not last_updated:
            role_state.emotions.last_updated_ts = now_ts
            return

        elapsed_minutes = int((now_ts - last_updated) / 60)
        if elapsed_minutes < 30:
            return

        decay_steps = min(4, elapsed_minutes // 30)
        emotions = role_state.emotions
        emotions.longing = max(0, emotions.longing - decay_steps)
        emotions.jealousy = max(0, emotions.jealousy - decay_steps)
        if emotions.comfort > 45:
            emotions.comfort = max(40, emotions.comfort - decay_steps)
        if role_state.relationship.relationship_level <= 3 and emotions.love > 35:
            emotions.love = max(30, emotions.love - decay_steps)
        emotions.clamp()
        emotions.last_updated_ts = now_ts

    def _apply_memory_influence(
        self,
        role_state: RoleState,
        ctx: InteractionContext,
    ) -> None:
        """Memory penting ikut memengaruhi emosi agar tidak terlalu linear."""

        summary = (role_state.last_conversation_summary or "").lower()
        if not summary:
            return

        emotions = role_state.emotions
        if ctx.tone == "DEEP" and any(keyword in summary for keyword in ["janji", "perasaan", "hubungan"]):
            emotions.comfort += 1
            emotions.love += 1
        if ctx.content == "ABSENCE" and any(keyword in summary for keyword in ["kangen", "rindu"]):
            emotions.longing += 2
        emotions.clamp()

    def _apply_emotion_formula(
        self,
        role_state: RoleState,
        ctx: InteractionContext,
    ) -> None:
        """Emotion = f(memory + input) dengan pengaruh kecil tapi stabil."""

        summary = (role_state.long_term_summary or "") + " " + (role_state.last_conversation_summary or "")
        lowered = summary.lower()
        emotions = role_state.emotions

        memory_weight = 0
        if any(token in lowered for token in ["janji", "percaya", "nyaman", "hubungan"]):
            memory_weight += 1
        if any(token in lowered for token in ["marah", "kecewa", "takut"]):
            memory_weight -= 1

        input_weight = 0
        if ctx.tone in ("SOFT", "DEEP"):
            input_weight += 1
        if ctx.tone in ("COLD", "CONFLICT"):
            input_weight -= 1

        emotions.comfort += memory_weight + max(0, input_weight)
        emotions.longing += 1 if ctx.content == "ABSENCE" else 0
        if input_weight < 0:
            emotions.jealousy += 1
        emotions.clamp()

    def _apply_emotional_drift(
        self,
        role_state: RoleState,
        ctx: InteractionContext,
    ) -> None:
        emotions = role_state.emotions
        delta = 0.0
        if ctx.tone == "DEEP":
            delta += 0.12
        elif ctx.tone in ("COLD", "CONFLICT"):
            delta -= 0.15
        elif ctx.tone == "PLAYFUL":
            delta += 0.04

        emotions.emotional_drift = (emotions.emotional_drift * 0.65) + delta
        emotions.clamp()

    def _update_emotion_layers(
        self,
        role_state: RoleState,
        ctx: InteractionContext,
    ) -> None:
        emotions = role_state.emotions

        secondary = Mood.NEUTRAL
        hidden = Mood.NEUTRAL

        if emotions.longing >= 55:
            secondary = Mood.TENDER
        elif emotions.jealousy >= 25:
            secondary = Mood.JEALOUS
        elif ctx.tone == "PLAYFUL":
            secondary = Mood.PLAYFUL

        if ctx.content == "APOLOGY":
            hidden = Mood.SAD
        elif emotions.jealousy >= 18 and emotions.mood != Mood.JEALOUS:
            hidden = Mood.JEALOUS
        elif emotions.comfort >= 65:
            hidden = Mood.TENDER

        emotions.secondary_mood = secondary
        emotions.hidden_mood = hidden
        emotions.clamp()

    def _apply_mood_inertia(
        self,
        role_state: RoleState,
        previous_mood: Mood,
        ctx: InteractionContext,
    ) -> None:
        """Jaga mood tidak meloncat terlalu cepat agar terasa persisten."""

        emotions = role_state.emotions
        current_mood = emotions.mood
        drift = emotions.emotional_drift

        if previous_mood == current_mood:
            return

        intense_previous = previous_mood in {Mood.SAD, Mood.ANNOYED, Mood.JEALOUS, Mood.TENDER}
        mild_context = ctx.strength <= 1 and ctx.tone in {"SOFT", "PLAYFUL"}

        if intense_previous and mild_context and abs(drift) < 0.2:
            emotions.secondary_mood = current_mood
            emotions.mood = previous_mood
            return

        if previous_mood == Mood.JEALOUS and current_mood == Mood.HAPPY:
            emotions.mood = Mood.TENDER
            emotions.secondary_mood = Mood.JEALOUS
            return

        if previous_mood == Mood.SAD and current_mood == Mood.PLAYFUL:
            emotions.mood = Mood.TENDER
            emotions.secondary_mood = Mood.PLAYFUL

    @staticmethod
    def _apply_natural_variation(role_state: RoleState) -> None:
        """Variasi kecil agar perubahan emosi tidak terlalu mekanis."""

        emotions = role_state.emotions
        roll = random.random()
        if roll < 0.18:
            emotions.comfort = max(0, min(100, emotions.comfort + random.choice([-1, 1])))
        elif roll < 0.30:
            emotions.longing = max(0, min(100, emotions.longing + random.choice([-1, 1])))
        emotions.clamp()
