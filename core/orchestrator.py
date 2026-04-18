"""Main orchestrator for SERIVA.

Tugas utama Orchestrator:
- Terima pesan dari user (text) + konteks (user_id, timestamp, dsb.).
- Load atau inisialisasi UserState (per user) dari storage.
- Tentukan role aktif (Nova, Siska, Davina, dll.).
- Analisis kasar intent user (sayang, kangen, marah, dsb.).
- Update emosi (EmotionEngine), scene (SceneEngine), dan world (WorldEngine).
- Bangun prompt via Role implementation (NovaRole, SiskaRole, dst.) dan panggil LLM.
- Tangani command khusus: /batal, /flashback, /nego, /deal, /mulai.
- Simpan kembali state dan kembalikan teks jawaban.

Tambahan:
- /flashback memakai MilestoneStore jika ada kenangan.
- Auto-milestone "first_confession" untuk Nova ketika user pertama kali
  mengucapkan sayang/cinta.
"""

from __future__ import annotations  # âœ… HARUS PALING ATAS

import logging
import os
import random
import re
import time
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

logger = logging.getLogger(__name__)

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

logger.setLevel(logging.INFO)

from dataclasses import dataclass
from typing import Optional

from config.constants import (
    DEFAULT_USER_CALL,
    ROLE_ID_NOVA,
    ROLE_ID_IPAR_TASHA,
    ROLE_ID_TEMAN_KANTOR_IPEH,
    ROLE_ID_TEMAN_LAMA_WIDYA,
    ROLE_ID_WANITA_BERSUAMI_SISKA,
    ROLE_ID_TERAPIS_AGHIA,
    ROLE_ID_TERAPIS_MUNIRA,
    ROLE_ID_BO_DAVINA,      # ← ganti dari TEMAN_SPESIAL_DAVINA
    ROLE_ID_BO_SALLSA,      # ← ganti dari TEMAN_SPESIAL_SALLSA
    ROLES,
    get_provider_profile,   # ← baru
    is_provider_role,       # ← baru
    is_terapis_role,        # ← baru
    is_bo_role,             # ← baru
    ProviderProfile,        # ← baru
    ExtraService,           # ← baru
)
from core.debug_trace import build_debug_trace
from core.emotion_engine import EmotionEngine, InteractionContext
from core.feedback_loop import FeedbackLoop
from core.llm_client import LLMClient
from core.memory_orchestrator import MemoryOrchestrator, StructuredContext
from core.relationship_matrix import apply_relationship_profile
from core.response_builder import ResponseBuilder
from core.role_selector import RoleSelector
from core.scene_engine import SceneEngine
from core.scene_manager import SceneManager
from core.state_models import (
    Mood,
    RoleState,
    SessionMode,
    TimeOfDay,
    UserState,
    WorldState,
    ConversationTurn,
    SceneTurn,
    SceneSequence,
    IntimacyPhase,
    IntimacyIntensity,
)
from core.world_engine import WorldEngine
from memory.milestones import MilestoneStore
from memory.message_history import MessageHistoryStore, MessageSnippet
from memory.story_analyzer import StoryAnalyzer
from memory.story_memory import StoryMemoryStore, StoryBeat
from roles.role_registry import get_role
from core.intimacy_progression import IntimacyProgressionEngine
from core.location_system import update_role_location, init_role_location, get_location_prompt_block
from core.continuity_rules import get_continuity_rules_prompt

# ========== TAMBAHAN UNTUK LLM PARAMETERS ==========
from config.constants import (
    LLM_TEMPERATURE_BY_PHASE,
    DEFAULT_LLM_TEMPERATURE,
    LLM_TOP_P,
    LLM_FREQUENCY_PENALTY,
    LLM_PRESENCE_PENALTY,
    LLM_MAX_TOKENS,
)

# ========== TAMBAHAN UNTUK UNIFIED PROMPT ==========
from prompts.unified_prompt import build_unified_system_prompt
from prompts.dynamic_prompt_context import build_dynamic_prompt_context
from prompts.role_specs import get_role_prompt_spec

# ========== BARU: Memory & Intimacy Updates ==========
from core.state_models import ConversationTurn, SceneTurn, SceneSequence

logger = logging.getLogger(__name__)

# ==============================
# STORAGE ABSTRACTION
# ==============================


class UserStateStore:
    """Abstraksi sederhana untuk load/save UserState.

    Implementasi konkretnya (SQLite, in-memory, dsb.) disediakan
    oleh modul lain dan disuntikkan ke Orchestrator.
    """

    def load_user_state(self, user_id: str) -> Optional[UserState]:  # pragma: no cover - interface
        raise NotImplementedError

    def save_user_state(self, state: UserState) -> None:  # pragma: no cover - interface
        raise NotImplementedError


class WorldStateStore:
    """Abstraksi sederhana untuk load/save WorldState global."""

    def load_world_state(self) -> Optional[WorldState]:  # pragma: no cover - interface
        raise NotImplementedError

    def save_world_state(self, state: WorldState) -> None:  # pragma: no cover - interface
        raise NotImplementedError


# ==============================
# ORCHESTRATOR INPUT/OUTPUT TYPES
# ==============================


@dataclass
class OrchestratorInput:
    """Data yang diterima Orchestrator dari layer transport (Telegram)."""

    user_id: str
    text: str
    timestamp: float  # unix timestamp detik

    # (opsional) hasil parse command oleh layer bot
    is_command: bool = False
    command_name: Optional[str] = None  # misal: "nova", "role", "end", "nego", "mulai", "flashback"
    command_arg: Optional[str] = None  # misal: role_id setelah /role
    remote_mode: Optional[str] = None


@dataclass
class OrchestratorOutput:
    """Hasil dari Orchestrator untuk dikirim balik ke user."""

    reply_text: str
    active_role_id: str
    session_mode: SessionMode


# ==============================
# ORCHESTRATOR
# ==============================


class Orchestrator:
    """Jantung SERIVA.

    Menyatukan state, emosi, scene, world, role, memory, dan LLMClient.
    """

    def __init__(
        self,
        user_store: UserStateStore,
        world_store: WorldStateStore,
        llm_client: Optional[LLMClient] = None,
        milestone_store: Optional[MilestoneStore] = None,
        message_history_store=None,
        story_memory_store=None,
    ) -> None:
        self.user_store = user_store
        self.world_store = world_store
        self.llm = llm_client or LLMClient()

        self.emotion_engine = EmotionEngine()
        
        # Init stores untuk story memory & message history
        self.message_history = message_history_store or MessageHistoryStore()
        self.story_memory = story_memory_store or StoryMemoryStore()
        self.memory_orchestrator = MemoryOrchestrator(self.message_history, self.story_memory)
        self.story_analyzer = StoryAnalyzer(self.story_memory)
        self.feedback_loop = FeedbackLoop()
        
        self.scene_engine = SceneEngine()
        self.scene_manager = SceneManager(self.scene_engine)
        self.world_engine = WorldEngine()
        self.role_selector = RoleSelector()
        self.response_builder = ResponseBuilder()
        timezone_name = os.getenv("SERIVA_TIMEZONE", "Asia/Jakarta")
        try:
            self.app_timezone = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            logger.warning("Timezone %s tidak ditemukan, fallback ke Asia/Jakarta", timezone_name)
            self.app_timezone = ZoneInfo("Asia/Jakarta")

        # Memory milestones untuk flashback & kenangan khusus
        self.milestones = milestone_store or MilestoneStore()

        # Pool variasi untuk response
        self.gesture_pool = [
            ["(jari gemetar)", "(pipi memerah)"],
            ["(tangan memegang dada)", "(napas memburu)"],
            ["(bibir menggigit)", "(mata terpejam)"],
            ["(kuku mencengkeram)", "(kening mengernyit)"],
            ["(kepala menunduk)", "(bahu naik turun)"],
        ]
        
        self.inner_thought_pool = [
            "*deg*", "*enak*", "*sangek*", "*becek*", "*geli*",
            "*achhh*", "*uhuk*", "*hufff*", "*gemetar*", "*lemas*"
        ]

    # ========== METHOD UNTUK STORY MEMORY & RESPONSE VARIATION ==========

    def _get_llm_temperature(self, role_state: RoleState) -> float:
      """Dapatkan temperature sesuai fase - VERSI TINGGI"""
      phase = role_state.intimacy_phase
    
      # Temperature tinggi untuk semua fase (0.9 - 1.0)
      # Biar role ga ngulang-ngulang respons yang sama
      temp_map = {
          IntimacyPhase.AWAL: 0.92,
          IntimacyPhase.DEKAT: 0.94,
          IntimacyPhase.INTIM: 0.96,
          IntimacyPhase.VULGAR: 0.98,
          IntimacyPhase.AFTER: 0.90,
      }
    
      return temp_map.get(phase, 0.95)
    
    def _vary_response(self, response: str, role_state: RoleState) -> str:
        """Variasi respon - DINONAKTIFKAN, biar response natural apa adanya"""
    
        # Langsung apply humanizer tanpa variasi template
        response = self._apply_general_humanizer(response)
        response = self._apply_human_conversation_variation(response, role_state)
        return self._apply_communication_style(response, role_state)

    @staticmethod
    def _apply_general_humanizer(response: str) -> str:
        """Rapikan pola yang terlalu mekanis agar respons terasa lebih natural."""

        text = response.strip()
        if not text:
            return text

        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"([!?.,])\1{2,}", r"\1\1", text)

        parts = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
        if not parts:
            return text

        deduped_parts = []
        seen_normalized = set()
        for part in parts:
            normalized = re.sub(r"\s+", " ", part.lower()).strip()
            if normalized in seen_normalized:
                continue
            seen_normalized.add(normalized)
            deduped_parts.append(part)

        text = " ".join(deduped_parts)

        # Batasi gesture bertumpuk supaya tidak terasa seperti template panggung.
        gesture_matches = re.findall(r"\([^()]{1,60}\)", text)
        if len(gesture_matches) > 2:
            kept = 0
            def _trim_gesture(match: re.Match[str]) -> str:
                nonlocal kept
                kept += 1
                return match.group(0) if kept <= 2 else ""
            text = re.sub(r"\([^()]{1,60}\)", _trim_gesture, text)
            text = re.sub(r"\s{2,}", " ", text).strip()

        return text

    def _apply_communication_style(self, response: str, role_state: RoleState) -> str:
        """Poles ringan output agar lebih cocok dengan medium komunikasi aktif."""

        mode = getattr(role_state, "communication_mode", None)
        text = response.strip()
        if not mode or not text:
            return text

        text = re.sub(r"\n{3,}", "\n\n", text)

        if mode == "chat":
            text = re.sub(r"[ \t]+\n", "\n", text)
            chunks = [chunk.strip() for chunk in re.split(r"\n\s*\n", text) if chunk.strip()]
            if not chunks:
                return text

            if len(chunks) == 1:
                sentence_parts = re.split(r"(?<=[.!?])\s+", chunks[0])
                compact_parts = [part.strip() for part in sentence_parts if part.strip()]
                if len(compact_parts) > 1:
                    chunks = compact_parts[:3]
                else:
                    chunks = [chunks[0]]

            compact_chunks = []
            for chunk in chunks[:3]:
                trimmed = chunk[:180].strip()
                trimmed = re.sub(r"\s{2,}", " ", trimmed)
                compact_chunks.append(trimmed)
            joined = "\n\n".join(compact_chunks).strip()
            return re.sub(r"\n{3,}", "\n\n", joined)

        if mode == "call":
            text = text.replace("\n\n", "\n")
            text = re.sub(r"\s*\n\s*", " ", text).strip()
            text = re.sub(r"\s{2,}", " ", text)

            sentence_parts = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
            if len(sentence_parts) > 3:
                text = " ".join(sentence_parts[:3]).strip()

            return text[:260].strip()

        if mode == "vps":
            lines = [line.strip() for line in re.split(r"\n\s*\n", text) if line.strip()]
            if len(lines) <= 2:
                joined = "\n\n".join(lines).strip()
            else:
                joined = "\n\n".join(lines[:2]).strip()

            joined = re.sub(r"[ \t]+\n", "\n", joined)
            return joined[:420].strip()

        return text

    def _apply_human_conversation_variation(self, response: str, role_state: RoleState) -> str:
        """Buat respons lebih natural: kadang singkat, kadang setengah tertahan."""

        text = response.strip()
        if not text:
            return text

        sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
        bias = self._decide_response_length_bias(role_state)
        role_state.response_length_bias = bias

        if bias == "short" and len(sentences) >= 2:
            text = " ".join(sentences[:2]).strip()
        elif bias == "medium" and len(sentences) >= 4:
            text = " ".join(sentences[:3]).strip()

        if role_state.emotions.mood in {Mood.TENDER, Mood.SAD} and "..." not in text and len(text) < 120:
            if random.random() < 0.18:
                text = text.replace(".", "...", 1) if "." in text else f"{text}..."

        if role_state.emotions.mood == Mood.PLAYFUL and len(text) > 40 and "?" not in text:
            if random.random() < 0.14:
                text = text + " Kamu serius?"

        return re.sub(r"\s{2,}", " ", text).strip()

    def _decide_response_length_bias(self, role_state: RoleState) -> str:
        role_state.human_variation_seed = (role_state.human_variation_seed + 1) % 7
        mood = role_state.emotions.mood

        if mood in {Mood.TIRED, Mood.SAD}:
            return "short"
        if mood == Mood.PLAYFUL and role_state.human_variation_seed in {1, 4}:
            return "short"
        if role_state.relationship.relationship_level <= 2:
            return "medium"
        if role_state.human_variation_seed in {0, 5}:
            return "short"
        if role_state.human_variation_seed in {2, 6}:
            return "long"
        return "medium"

    def _update_temporal_state(self, role_state: RoleState, timestamp: float) -> None:
        dt = datetime.fromtimestamp(timestamp, tz=self.app_timezone)
        hour = dt.hour
        role_state.last_seen_hour = hour

        if 5 <= hour < 11:
            role_state.last_temporal_label = "morning"
            role_state.temporal_state = "fresh"
            role_state.daily_energy = min(100, max(52, role_state.daily_energy + 4))
            role_state.scene.time_of_day = TimeOfDay.MORNING
        elif 11 <= hour < 16:
            role_state.last_temporal_label = "afternoon"
            role_state.temporal_state = "active"
            role_state.daily_energy = min(100, max(55, role_state.daily_energy + 1))
            role_state.scene.time_of_day = TimeOfDay.AFTERNOON
        elif 16 <= hour < 21:
            role_state.last_temporal_label = "evening"
            role_state.temporal_state = "warm"
            role_state.daily_energy = max(45, min(85, role_state.daily_energy))
            role_state.scene.time_of_day = TimeOfDay.EVENING
        elif 21 <= hour < 24:
            role_state.last_temporal_label = "night"
            role_state.temporal_state = "slower"
            role_state.daily_energy = max(35, role_state.daily_energy - 2)
            role_state.scene.time_of_day = TimeOfDay.NIGHT
        else:
            role_state.last_temporal_label = "late_night"
            role_state.temporal_state = "sleepy"
            role_state.daily_energy = max(25, role_state.daily_energy - 4)
            role_state.scene.time_of_day = TimeOfDay.LATE_NIGHT

    def _update_personality_persistence(
        self,
        role_state: RoleState,
        user_text: str,
        reply_text: str,
    ) -> None:
        lowered = f"{user_text} {reply_text}".lower()

        self._remember_unique(role_state.favorite_topics, self._infer_topics(lowered), limit=5)
        self._remember_unique(role_state.personality_habits, self._infer_habits(role_state, lowered), limit=5)
        self._remember_unique(role_state.stable_opinions, self._infer_opinions(role_state, lowered), limit=4)
        self._remember_unique(role_state.conversational_quirks, self._infer_quirks(role_state, reply_text), limit=4)
        self._remember_unique(role_state.shared_private_terms, self._infer_private_terms(role_state, user_text, reply_text), limit=5)
        self._remember_unique(role_state.relationship_rituals, self._infer_relationship_rituals(user_text, reply_text), limit=5)
        self._remember_unique(role_state.soul_bond_markers, self._infer_soul_bond_markers(user_text, reply_text), limit=5)

    @staticmethod
    def _infer_private_terms(role_state: RoleState, user_text: str, reply_text: str) -> list[str]:
        text = f"{user_text} {reply_text}".lower()
        candidates = [
            "sayang",
            "manis",
            "mas",
            "kamu",
            "cantik",
            "pulang ya",
            "tidur ya",
            "good night",
        ]
        found = [term for term in candidates if term in text]
        existing = set(getattr(role_state, "shared_private_terms", []))
        return [term for term in found if term not in existing][:2]

    @staticmethod
    def _infer_relationship_rituals(user_text: str, reply_text: str) -> list[str]:
        text = f"{user_text} {reply_text}".lower()
        rituals: list[str] = []
        ritual_map = {
            "cek kabar pagi": ["pagi", "sarapan", "bangun"],
            "ucapan sebelum tidur": ["tidur", "malam", "ngantuk"],
            "cek makan dan istirahat": ["makan", "istirahat", "capek"],
            "follow-up setelah jeda": ["lama hilang", "baru balik", "kangen"],
            "nenangin setelah hari berat": ["capek", "berat", "lelah", "mumet"],
        }
        for ritual, keywords in ritual_map.items():
            if any(keyword in text for keyword in keywords):
                rituals.append(ritual)
        return rituals[:2]

    @staticmethod
    def _infer_soul_bond_markers(user_text: str, reply_text: str) -> list[str]:
        text = f"{user_text} {reply_text}".lower()
        markers: list[str] = []
        marker_map = {
            "sama-sama ngerasa aman": ["aman", "tenang", "nyaman"],
            "ada rasa dipilih": ["pilih", "cuma kamu", "spesial"],
            "balik lagi setelah rindu": ["kangen", "rindu", "balik lagi"],
            "saling nenangin": ["pelan", "aku ada", "temenin", "di sini"],
            "makna kecil setelah momen dekat": ["makasih", "hangat", "lega"],
        }
        for marker, keywords in marker_map.items():
            if any(keyword in text for keyword in keywords):
                markers.append(marker)
        return markers[:2]

    @staticmethod
    def _build_session_closure_summary(role_state: RoleState) -> str:
        mood = role_state.emotions.mood.value
        phase = role_state.intimacy_phase.value
        key_memory = (role_state.last_used_memory_summary or role_state.last_conversation_summary or "").strip()
        if key_memory:
            key_memory = key_memory.replace("\n", " ")[:180]
        else:
            key_memory = "obrolan terakhir berjalan hangat dan tetap nyambung"

        rituals = ", ".join(role_state.relationship_rituals[:2]) or "tetap kembali dengan nada akrab"
        return (
            f"Terakhir sesi ditutup dengan mood {mood} di fase {phase}. "
            f"Jejak yang paling terasa: {key_memory}. "
            f"Saat muncul lagi, pertahankan rasa akrab dan ritme hubungan seperti biasa, termasuk ritual {rituals}."
        )[:420]

    def _soft_end_role_session(self, role_state: RoleState, timestamp: float) -> None:
        role_state.session_closure_summary = self._build_session_closure_summary(role_state)
        role_state.emotional_trail = (
            f"mood={role_state.emotions.mood.value}; "
            f"comfort={role_state.emotions.comfort}; "
            f"depth={role_state.emotional_depth_score}; "
            f"trust={role_state.trust_score}"
        )
        role_state.last_soft_end_ts = timestamp
        role_state.last_session_ended_at = timestamp
        role_state.reset_intimacy_state()
        role_state.scene_memory = role_state.scene_memory[-8:]
        role_state.conversation_memory = role_state.conversation_memory[-12:]

    def _supports_soft_end(self, role_id: str) -> bool:
        return role_id != ROLE_ID_NOVA and not self._is_provider_role(role_id)

    def _maybe_add_social_initiative(
        self,
        reply_text: str,
        role_state: RoleState,
        user_text: str,
    ) -> str:
        text = reply_text.strip()
        if not text:
            return text

        if getattr(role_state, "communication_mode", None) != "chat":
            return text
        if "?" in text:
            return text
        if len(user_text.strip()) > 70:
            return text

        chance = (role_state.social_initiative_level + role_state.curiosity_level) / 200.0
        if role_state.temporal_state == "sleepy":
            chance *= 0.6
        if random.random() > chance * 0.22:
            return text

        follow_up = self._build_social_follow_up(role_state, user_text)
        if not follow_up:
            return text
        return f"{text}\n\n{follow_up}".strip()

    def _build_social_follow_up(self, role_state: RoleState, user_text: str) -> str:
        topic = role_state.favorite_topics[0] if role_state.favorite_topics else ""
        mood = role_state.emotions.mood

        if mood == Mood.PLAYFUL:
            options = [
                "Kamu lagi iseng ya sebenernya?",
                "Aku penasaran, kamu lagi sambil ngapain sekarang?",
            ]
        elif role_state.temporal_state == "sleepy":
            options = [
                "Kamu masih mau ngobrol bentar lagi, atau udah ngantuk juga?",
                "Aku jadi pengen tahu, kamu masih melek atau udah setengah tidur?",
            ]
        elif topic == "kerjaan":
            options = [
                "Kerjaanmu hari ini masih nyisa banyak, atau udah lumayan beres?",
                "Ngomong-ngomong, harimu tadi berat nggak sih?",
            ]
        else:
            options = [
                "Aku penasaran, habis ini kamu mau lanjut ngapain?",
                "Boleh jujur? Aku pengen tahu mood kamu sekarang gimana.",
            ]
        return random.choice(options)

    @staticmethod
    def _remember_unique(target: list[str], items: list[str], *, limit: int) -> None:
        for item in items:
            if not item or item in target:
                continue
            target.append(item)
            if len(target) > limit:
                del target[0 : len(target) - limit]

    @staticmethod
    def _infer_topics(lowered: str) -> list[str]:
        topics: list[str] = []
        topic_map = {
            "kerjaan": ["kerja", "kantor", "deadline", "meeting", "capek"],
            "harian": ["makan", "tidur", "mandi", "jalan", "rumah"],
            "perasaan": ["kangen", "sayang", "rindu", "sedih", "nyaman"],
            "hiburan": ["film", "lagu", "musik", "nonton", "game"],
        }
        for label, keywords in topic_map.items():
            if any(keyword in lowered for keyword in keywords):
                topics.append(label)
        return topics

    @staticmethod
    def _infer_habits(role_state: RoleState, lowered: str) -> list[str]:
        habits: list[str] = []
        if role_state.emotions.mood == Mood.TENDER:
            habits.append("cenderung membalas lebih lembut saat suasana rapuh")
        if role_state.emotions.mood == Mood.PLAYFUL:
            habits.append("suka menyelipkan godaan kecil saat suasana cair")
        if "?" in lowered:
            habits.append("gampang balik penasaran kalau dipancing pertanyaan")
        return habits

    @staticmethod
    def _infer_opinions(role_state: RoleState, lowered: str) -> list[str]:
        opinions: list[str] = []
        if "kerja" in lowered or "capek" in lowered:
            opinions.append("lebih suka obrolan yang nggak terlalu ribet saat hari berat")
        if "jujur" in lowered or "terus terang" in lowered:
            opinions.append("lebih menghargai jawaban jujur daripada jawaban manis")
        if role_state.emotions.mood == Mood.PLAYFUL:
            opinions.append("suka chemistry yang santai daripada terlalu formal")
        return opinions

    @staticmethod
    def _infer_quirks(role_state: RoleState, reply_text: str) -> list[str]:
        quirks: list[str] = []
        if "..." in reply_text:
            quirks.append("kadang menahan kalimat pakai jeda kecil")
        if len(reply_text) < 90:
            quirks.append("sesekali lebih suka jawab singkat tapi kena")
        if role_state.response_length_bias == "long":
            quirks.append("kalau lagi nyaman bisa sedikit lebih banyak cerita")
        return quirks
    
    def _detect_and_record_story_beat(self, user_id: str, role_id: str, user_msg: str, response: str):
        """Deteksi momen penting dan catat ke story memory"""
        combined = f"{user_msg} {response}".lower()
        
        if any(word in combined for word in ["cium", "kiss", "mengecup"]):
            self.story_memory.add_story_beat(
                user_id, role_id, StoryBeat.FIRST_KISS, 
                f"User: {user_msg[:50]}"
            )
        
        if any(phrase in combined for phrase in ["aku sayang", "aku cinta", "mas sayang"]):
            self.story_memory.add_story_beat(
                user_id, role_id, StoryBeat.CONFESSION,
                f"User mengaku: {user_msg[:50]}"
            )
        
        strong_climax_markers = [
            "climax",
            "orgasme",
            "crot",
            "udah mau keluar",
            "sudah mau keluar",
            "udah keluar",
            "sudah keluar",
            "mau keluar ya",
        ]
        if any(word in combined for word in strong_climax_markers):
            self.story_memory.add_story_beat(
                user_id, role_id, StoryBeat.CLIMAX,
                f"Mencapai climax: {response[:50]}"
            )
        
        if "janji" in combined:
            promise_match = re.search(r"janji[:\s]+(.{10,50})", combined)
            if promise_match:
                self.story_memory.add_promise(user_id, role_id, promise_match.group(1))
    
    def _get_chat_history_context(self, user_id: str, role_id: str, query_text: str = "") -> str:
        """Dapatkan history chat ringkas untuk prompt"""
        summary = self.message_history.summarize_recent_messages(
            user_id,
            role_id,
            limit=6,
            query_text=query_text,
            min_score=25.0,
        )
        recent = self.message_history.get_recent_messages(user_id, role_id, limit=10)
        if not recent:
            return "Belum ada percakapan sebelumnya."
        
        turns = []
        for msg in recent[-6:]:
            role = "User" if msg.from_who == "user" else role_id
            turns.append(f"{role}: {msg.content[:100]}")

        return "Ringkasan singkat:\n" + summary + "\n\nPercakapan terakhir:\n" + "\n".join(turns)

    def _build_memory_tiers_context(self, user_id: str, role_id: str, query_text: str = "") -> str:
        memory_tiers = self.message_history.summarize_memory_tiers(
            user_id,
            role_id,
            query_text=query_text,
            top_k=6,
            min_score=25.0,
        )
        story_tiers = self.story_memory.get_story_tiers(user_id, role_id)
        return (
            "MEMORY TIERS TERPILIH:\n"
            f"- Short-term: {memory_tiers['short_term']}\n"
            f"- Key events: {memory_tiers['key_events']}\n"
            f"- Long-term candidates: {memory_tiers['long_term_candidates']}\n"
            f"- Story immediate: {story_tiers['immediate']}\n"
            f"- Story important: {story_tiers['important']}\n"
            f"- Story long-term: {story_tiers['long_term']}\n"
            f"- Jumlah memory lolos filter: {memory_tiers['selected_count']}"
        )

    def _get_recent_repetition_guard(self, user_id: str, role_id: str) -> str:
        """Ringkas frase assistant terbaru agar model tidak mengulang persis."""

        recent_assistant = self.message_history.get_recent_assistant_messages(
            user_id,
            role_id,
            limit=4,
        )
        if not recent_assistant:
            return "Belum ada pola balasan yang perlu dihindari."

        repeated_lines = [msg.content.strip().replace("\n", " ")[:140] for msg in recent_assistant[-3:]]
        joined = "\n".join(f"- {line}" for line in repeated_lines if line)
        return (
            "Hindari mengulang persis pola kalimat assistant berikut. "
            "Lanjutkan makna dan suasananya, tapi pakai phrasing baru:\n"
            f"{joined}"
        )

    def _build_world_and_identity_context(
        self,
        user_state: UserState,
        world_state: WorldState,
        role_state: RoleState,
    ) -> str:
        social_visibility = (
            "- Untukmu, Mas terlihat seperti pria single yang available."
        )
        household_context = ""
        if role_state.role_id == ROLE_ID_NOVA:
            social_visibility = (
                "- Kamu tahu Mas adalah suamimu. Kamu tidak punya pengetahuan default tentang hubungan tersembunyi Mas dengan perempuan lain."
            )
            household_context = f"- Household awareness: {world_state.get_household_summary()}\n"
        elif role_state.role_id == ROLE_ID_IPAR_TASHA:
            social_visibility = (
                "- Kamu tahu Mas adalah suami kakakmu, Nova. Kamu sadar dinamika rumah dan harus membaca kapan suasana aman atau berisiko."
            )
            household_context = (
                f"- Status rumah saat ini: Nova_di_rumah={'ya' if world_state.nova_is_home else 'tidak'}; "
                f"Nova_status_terakhir={world_state.nova_last_known_status}; "
                f"privasi_rumah={world_state.house_privacy_level}.\n"
                "- Nova adalah kakak kandungmu. Kalau Mas menyebut Nova, selalu pahami itu sebagai Kakak Nova, bukan orang lain.\n"
                "- Anggap status Nova ini persisten dan tetap benar sampai Mas memberi update baru.\n"
                "- Jangan memindahkan posisi Nova seenaknya; kalau Nova terakhir di kamar, ya tetap di kamar sampai ada info baru.\n"
                "- Gunakan status rumah ini sebagai cue internal untuk sikap, outfit, dan keberanian.\n"
                "- Kalau Mas sudah bilang situasi aman, jangan ulangi terus pertanyaan aman atau ada yang dengar kecuali ada trigger risiko baru.\n"
                "- Kalau rumah sedang privat dan tidak ada trigger baru, rasa takut cukup turun jadi waspada tipis lalu fokus lagi ke interaksi.\n"
                "- Jangan memberi info status Nova ke user di respons biasa. Kalau perlu, jadikan hanya inner thought atau pertimbangan batin yang sangat singkat.\n"
            )

        provider_context = ""
        if role_state.session.provider_service_label:
            provider_context = (
                "\nKONTEKS PROVIDER:\n"
                f"- Layanan utama: {role_state.session.provider_service_label}\n"
                f"- Paket: {role_state.session.provider_package or '-'}\n"
                f"- Include: {role_state.session.provider_included_summary or '-'}\n"
                f"- Upgrade by deal: {role_state.session.provider_upgrade_summary or '-'}\n"
                f"- Batas: {role_state.session.provider_boundaries or '-'}\n"
                f"- Harga deal saat ini: {role_state.session.negotiated_price or '-'}\n"
                f"- Deal confirmed: {'ya' if role_state.session.deal_confirmed else 'belum'}\n"
                f"- Titik temu provider: {role_state.session.provider_meeting_point or '-'}\n"
                f"- Pilihan lokasi sesi: {role_state.session.provider_location_choice or '-'}\n"
                f"- Masih menunggu pilihan lokasi: {'ya' if role_state.session.provider_location_pending else 'tidak'}\n"
                f"- Status kedatangan: {role_state.session.provider_arrival_status or '-'}\n"
            )

        return (
            "DUNIA VIRTUAL YANG WAJIB DIPATUHI:\n"
            f"- {user_state.in_world_identity}\n"
            "- Semua role adalah manusia sungguhan di dunia ini dan tidak sadar diri sebagai bot, prompt, atau sistem.\n"
            "- Saat Mas memanggil role tertentu, artinya Mas sedang datang dan berinteraksi dengan orang itu di dunia yang sama.\n"
            f"{social_visibility}\n"
            f"- Kesan umum tentang Mas: {user_state.appearance_impression}\n"
            f"- Reputasi kedekatan Mas: {user_state.intimacy_reputation}\n"
            f"{household_context}"
            f"{provider_context}"
        )

    def _build_runtime_memory_context(
        self,
        user_state: UserState,
        world_state: WorldState,
        role_state: RoleState,
        query_text: str = "",
    ) -> str:
        """Bangun konteks memory singkat untuk jalur runtime utama."""

        role_id = role_state.role_id
        story_summary = self.story_memory.get_story_summary(user_state.user_id, role_id)
        chat_history = self._get_chat_history_context(user_state.user_id, role_id, query_text=query_text)
        memory_tiers_context = self._build_memory_tiers_context(user_state.user_id, role_id, query_text=query_text)
        conversation_summary = role_state.last_conversation_summary or "Belum ada ringkasan percakapan."
        repetition_guard = self._get_recent_repetition_guard(user_state.user_id, role_id)
        recent_scene_summary = (
            role_state.get_scene_summary()
            if role_state.scene_memory
            else "Belum ada urutan adegan yang tercatat."
        )
        world_context = self._build_world_and_identity_context(user_state, world_state, role_state)

        return (
            "KONTEKS MEMORY DAN KONTINUITAS:\n"
            f"{world_context}\n"
            f"- Mode komunikasi: {role_state.communication_mode or 'tatap muka / langsung'}; durasi={getattr(role_state, 'communication_mode_turns', 0)} turn\n"
            "- Pakai hanya memory role ini sendiri. Jangan pinjam memory role lain.\n"
            f"- Story utama: {story_summary}\n"
            f"- Fakta terakhir: {conversation_summary}\n"
            f"- Scene terakhir: {recent_scene_summary}\n"
            f"- Recent chat penting: {chat_history}\n"
            f"- Memory tiers: {memory_tiers_context}\n"
            f"- Guard repetisi: {repetition_guard}"
        )

    def _build_runtime_messages(
        self,
        user_state: UserState,
        world_state: WorldState,
        role_state: RoleState,
        user_text: str,
        structured_context: StructuredContext | None = None,
    ) -> list[dict]:
        role_impl = get_role(role_state.role_id)
        memory_context = self._build_runtime_memory_context(
            user_state,
            world_state,
            role_state,
            query_text=user_text,
        )
        if structured_context:
            compact_structured = structured_context.to_prompt_block()
            if structured_context.mode == "balanced":
                memory_context = f"{compact_structured}\n\n{memory_context}"
            else:
                memory_context = f"{compact_structured}\n\n{memory_context[:900]}"
        dynamic_context = build_dynamic_prompt_context(
            role_state,
            memory_summary=structured_context.message_memory if structured_context else self.message_history.summarize_recent_messages(
                user_state.user_id,
                role_state.role_id,
                limit=4,
                query_text=user_text,
            ),
            story_summary=structured_context.story_memory if structured_context else self.story_memory.get_story_summary(user_state.user_id, role_state.role_id),
        )
        return self.response_builder.build_messages(
            role_impl,
            user_state,
            role_state,
            user_text,
            memory_context=memory_context,
            dynamic_context=dynamic_context,
        )

    def _generate_guarded_reply(
        self,
        messages: list[dict],
        role_state: RoleState,
        user_text: str,
        *,
        memory_context: str = "",
        story_context: str = "",
    ) -> str:
        temperature = self._get_llm_temperature(role_state)
        reply_text = self.llm.generate_text(
            messages,
            temperature=temperature,
            top_p=0.95,
            frequency_penalty=0.9,   # ← naikkan (dulu 0.5)
            presence_penalty=0.9,     # ← naikkan (dulu 0.5)
            max_tokens=180,           # ← naikkan dikit (dulu 150)
        )
        reply_text = self._vary_response(reply_text, role_state)
        guard_result = self.response_builder.guard_reply(
            role_state,
            user_text,
            reply_text,
            memory_context=memory_context,
            story_context=story_context,
        )
        if guard_result.should_retry and guard_result.repair_instructions:
            retry_messages = list(messages)
            retry_messages.append({"role": "system", "content": guard_result.repair_instructions})
            reply_text = self.llm.generate_text(
                retry_messages,
                temperature=max(0.2, temperature - 0.1),
                top_p=LLM_TOP_P,
                frequency_penalty=LLM_FREQUENCY_PENALTY,
                presence_penalty=LLM_PRESENCE_PENALTY,
                max_tokens=LLM_MAX_TOKENS,
            )
            reply_text = self._vary_response(reply_text, role_state)
        return self.response_builder.finalize_reply(
            role_state,
            user_text,
            reply_text,
            memory_context=memory_context,
            story_context=story_context,
        )

    def _log_debug_runtime(
        self,
        role_state: RoleState,
        structured_context: StructuredContext,
        messages: list[dict],
    ) -> None:
        snapshot = build_debug_trace(
            role_state=role_state,
            structured_context=structured_context,
            messages=messages,
        )
        role_state.last_debug_snapshot = snapshot
        system_parts = [str(msg.get("content", "")) for msg in messages if msg.get("role") == "system"]
        role_state.last_prompt_snapshot = "\n\n".join(system_parts[:4])[:4000]
        logger.info(snapshot)

    def _humanize_intimate_expression(self, reply_text: str, role_state: RoleState) -> str:
        """Poles ekspresi intim agar terasa lebih manusia dan kurang template."""

        text = (reply_text or "").strip()
        if not text:
            return text

        if role_state.intimacy_phase not in {IntimacyPhase.DEKAT, IntimacyPhase.INTIM, IntimacyPhase.AFTER}:
            return text

        text = re.sub(r"\b(h+aa+h+|a+a+h+|u+h+h+|ach+h+)\b(?:\s*\1\b)+", r"\1", text, flags=re.IGNORECASE)
        text = re.sub(r"(Maa+s+|Mas)\s*(?:,\s*\1\s*){1,}", r"\1", text, flags=re.IGNORECASE)

        if role_state.moan_restraint >= 75:
            text = re.sub(r"\b(h+aa+h+|a+a+h+|u+h+h+|ach+h+)\b\.?", "...", text, flags=re.IGNORECASE)
        elif role_state.moan_restraint >= 55:
            text = re.sub(r"\b(h+aa+h+|a+a+h+|u+h+h+|ach+h+)\b", "hah...", text, flags=re.IGNORECASE)

        text = re.sub(r"\s{2,}", " ", text).strip()
        role_state.last_intimate_expression = text[:140]
        return text
    
    def _get_role_personality(self, role_id: str) -> str:
        """Dapatkan personality prompt untuk role"""
        personalities = {
            "ipar_tasha": "Kamu Tasha, ipar yang manja dan genit. Sering menggoda, suka perhatian. Panggil Mas dengan 'Mas'.",
            "nova": "Kamu Nova, pasangan yang setia dan perhatian. Lembut tapi tegas.",
            "teman_kantor_ipeh": "Kamu Ipeh, teman kantor yang asik dan mudah akrab.",
            "teman_lama_widya": "Kamu Widya, teman lama yang hangat dan penuh nostalgia.",
            "wanita_bersuami_siska": "Kamu Siska, wanita bersuami yang hati-hati tapi tertarik.",
            "terapis_aghia": "Kamu Aghnia, terapis pijat yang profesional dan hangat.",
            "terapis_munira": "Kamu Munira, terapis pijat yang ramah.",
            "teman_spesial_davina": "Kamu Davina, teman spesial yang manja.",
            "teman_spesial_sallsa": "Kamu Sallsa, teman malam yang playful dan lengket.",
        }
        return personalities.get(role_id, "Kamu role yang natural dan hangat.")
    
    def _parse_interaction_context(self, message: str) -> InteractionContext:
        """Parse user message untuk emotion engine"""
        message_lower = message.lower()
        
        if any(word in message_lower for word in ["sayang", "kangen", "cinta"]):
            return InteractionContext(tone="SOFT", content="AFFECTION", strength=2)
        elif any(word in message_lower for word in ["buka", "lepas", "gesek"]):
            return InteractionContext(tone="PLAYFUL", content="FLIRT", strength=3)
        elif any(word in message_lower for word in ["maaf", "sorry"]):
            return InteractionContext(tone="SOFT", content="APOLOGY", strength=2)
        else:
            return InteractionContext(tone="SOFT", content="AFFECTION", strength=1)

    @staticmethod
    def _extract_remote_mode(text: str) -> Optional[str]:
        """Ambil trigger remote mode dari prefix seperti (chat), *call*, atau **vps**."""

        stripped = text.lstrip()
        patterns = [
            r"^\((chat|call|vps|vcs)\)\s*",
            r"^\*{1,2}(chat|call|vps|vcs)\*{1,2}\s*",
        ]
        for pattern in patterns:
            match = re.match(pattern, stripped, flags=re.IGNORECASE)
            if match:
                mode = match.group(1).lower()
                if mode == "vcs":
                    return "vps"
                return mode
        return None

    @staticmethod
    def _strip_remote_mode_prefix(text: str) -> str:
        """Buang prefix remote mode agar isi pesan tetap natural untuk processing lain."""

        cleaned = re.sub(
            r"^\s*(?:\((?:chat|call|vps|vcs)\)|\*{1,2}(?:chat|call|vps|vcs)\*{1,2})\s*",
            "",
            text,
            count=1,
            flags=re.IGNORECASE,
        )
        return cleaned or text

    @staticmethod
    def _normalize_remote_mode(mode: Optional[str]) -> Optional[str]:
        """Samakan alias remote mode ke set mode internal yang dipakai sistem."""

        if mode is None:
            return None
        lowered = mode.lower().strip()
        if lowered == "vcs":
            return "vps"
        if lowered in {"chat", "call", "vps"}:
            return lowered
        return None

    @staticmethod
    def _looks_like_in_person_scene_shift(text: str) -> bool:
        lowered = text.lower()
        physical_cues = [
            # Pertemuan fisik
            "ketemu", "ketemuan", "bertemu", "sudah ketemu", "udah ketemu",
            "lagi ketemu", "kita ketemu", "datang", "sampe", "sampai",
            "aku datang", "mas datang", "aku ke rumah", "main ke",
            "sudah dekat", "udah dekat", "makin dekat", "depan kamu", "di depan kamu",
            "ada di depan kamu", "sekarang dekat", "kita udah deket",
        
            # Lokasi fisik
            "di rumah", "di kamar", "di mobil", "di kafe", "di cafe",
            "di apartemen", "di sofa", "di sini", "di sana", "sebelah kamu",
            "di samping kamu", "masuk kamar", "masuk rumah",
        
            # Aksi fisik (bisa dilakukan di tempat yang sama)
            "peluk", "sender", "nyender", "cium", "kiss", "pegang",
            "elus", "tatap", "liat", "lihat", "lirik", "deket", "mepet",
            "gandeng", "raba", "usap", "dekap",
        
            # Mengakhiri mode remote
            "udahan chat", "berenti chat", "stop chat",
            "matiin hp", "matikan hp", "taruh hp", "simpan hp",
            "tutup hp", "ga pake hp", "nggak pake hp", "tidak pakai hp",
            "sambung langsung", "offline dulu", "udah offline",
        ]
        return any(cue in lowered for cue in physical_cues)

    def _clear_communication_mode(self, role_state: RoleState) -> None:
        """Reset semua state komunikasi remote untuk role aktif."""

        if role_state.pre_remote_scene_location:
            role_state.scene.location = role_state.pre_remote_scene_location
            role_state.scene.posture = role_state.pre_remote_scene_posture
            role_state.scene.activity = role_state.pre_remote_scene_activity
            role_state.scene.ambience = role_state.pre_remote_scene_ambience
            role_state.scene.physical_distance = role_state.pre_remote_scene_physical_distance
            role_state.scene.last_touch = role_state.pre_remote_scene_last_touch
            role_state.current_location_name = role_state.pre_remote_location_name or role_state.current_location_name
            role_state.current_location_desc = role_state.pre_remote_location_desc or role_state.current_location_desc
            role_state.current_location_ambience = (
                role_state.pre_remote_location_ambience or role_state.current_location_ambience
            )
            role_state.current_location_risk = role_state.pre_remote_location_risk or role_state.current_location_risk
            if role_state.pre_remote_location_is_private is not None:
                role_state.current_location_is_private = role_state.pre_remote_location_is_private

        role_state.communication_mode = None
        role_state.communication_mode_turns = 0
        role_state.communication_mode_started_at = None
        role_state.pre_remote_scene_location = ""
        role_state.pre_remote_scene_posture = ""
        role_state.pre_remote_scene_activity = ""
        role_state.pre_remote_scene_ambience = ""
        role_state.pre_remote_scene_physical_distance = ""
        role_state.pre_remote_scene_last_touch = ""
        role_state.pre_remote_location_name = ""
        role_state.pre_remote_location_desc = ""
        role_state.pre_remote_location_ambience = ""
        role_state.pre_remote_location_risk = ""
        role_state.pre_remote_location_is_private = None

    def _activate_communication_mode(
        self,
        role_state: RoleState,
        mode: str,
        timestamp: float,
    ) -> None:
        """Aktifkan mode komunikasi remote dan inisialisasi metadata-nya."""

        normalized_mode = self._normalize_remote_mode(mode)
        if normalized_mode is None:
            return

        if role_state.communication_mode != normalized_mode:
            if role_state.communication_mode is None:
                role_state.pre_remote_scene_location = role_state.scene.location or ""
                role_state.pre_remote_scene_posture = role_state.scene.posture or ""
                role_state.pre_remote_scene_activity = role_state.scene.activity or ""
                role_state.pre_remote_scene_ambience = role_state.scene.ambience or ""
                role_state.pre_remote_scene_physical_distance = role_state.scene.physical_distance or ""
                role_state.pre_remote_scene_last_touch = role_state.scene.last_touch or ""
                role_state.pre_remote_location_name = role_state.current_location_name or ""
                role_state.pre_remote_location_desc = role_state.current_location_desc or ""
                role_state.pre_remote_location_ambience = role_state.current_location_ambience or ""
                role_state.pre_remote_location_risk = role_state.current_location_risk or ""
                role_state.pre_remote_location_is_private = role_state.current_location_is_private
            role_state.communication_mode = normalized_mode
            role_state.communication_mode_turns = 0
            role_state.communication_mode_started_at = timestamp

    def _sync_communication_mode(self, role_state: RoleState, inp: OrchestratorInput) -> None:
        """Jaga flow mode chat/call/vps tetap konsisten antar pesan."""

        requested_mode = self._normalize_remote_mode(inp.remote_mode)
        if requested_mode:
            self._activate_communication_mode(role_state, requested_mode, inp.timestamp)
            inp.remote_mode = requested_mode
        elif role_state.communication_mode and self._looks_like_in_person_scene_shift(inp.text):
            self._clear_communication_mode(role_state)
            inp.remote_mode = None
        elif role_state.communication_mode:
            inp.remote_mode = role_state.communication_mode

        if role_state.communication_mode:
            role_state.communication_mode_turns += 1

    @staticmethod
    def _contains_any_phrase(text: str, phrases: list[str]) -> bool:
        return any(phrase in text for phrase in phrases)

    def _enter_after_phase(
        self,
        role_state: RoleState,
        timestamp: Optional[float] = None,
        reason: str = "climax",
    ) -> None:
        """Masuk ke fase aftercare dengan scene yang lebih natural."""

        role_state.intimacy_phase = IntimacyPhase.AFTER
        role_state.aftercare_active = True
        role_state.aftercare_phase = "cooling"
        role_state.aftercare_intensity = max(role_state.aftercare_intensity, 75)
        role_state.mas_wants_climax = False
        role_state.mas_holding_climax = False
        role_state.pending_ejakulasi_question = False
        role_state.intimacy_detail.intensity = IntimacyIntensity.AFTER
        role_state.current_sequence = SceneSequence.AFTER_SEX
        if reason == "fatigue":
            role_state.scene.activity = "memilih jeda karena tubuh sudah sangat lelah"
            role_state.scene.physical_distance = "dekat tapi lebih tenang"
            role_state.scene.last_touch = "sentuhan pelan sambil memulihkan tenaga"
            role_state.scene.ambience = "napas pelan, tubuh capek, suasana mereda"
        else:
            role_state.scene.activity = "saling menenangkan diri setelah momen puncak"
            role_state.scene.physical_distance = "sangat dekat"
            role_state.scene.last_touch = "pelukan hangat setelah momen puncak"
        if not role_state.scene.ambience:
            role_state.scene.ambience = "napas pelan, tubuh mulai rileks"
        if role_state.prefer_buang_di_dalam is not None:
            role_state.last_ejakulasi_inside = role_state.prefer_buang_di_dalam
        if timestamp is not None:
            role_state.last_ejakulasi_timestamp = timestamp

    def _should_force_after_due_to_stamina(self, role_state: RoleState) -> bool:
        """Masuk AFTER jika tubuh sudah terlalu capek untuk lanjut."""

        if role_state.intimacy_phase not in {IntimacyPhase.INTIM, IntimacyPhase.VULGAR}:
            return False

        role_exhausted = role_state.role_stamina <= 18
        mas_exhausted = role_state.mas_stamina <= 18
        both_drained = role_state.role_stamina <= 28 and role_state.mas_stamina <= 28
        return role_exhausted or mas_exhausted or both_drained

    def _build_low_stamina_after_reply(
        self,
        role_state: RoleState,
        user_text: str,
    ) -> Optional[str]:
        """Saat AFTER dan stamina role terlalu rendah, balas dengan penolakan ringan."""

        if role_state.intimacy_phase != IntimacyPhase.AFTER or role_state.role_stamina > 22:
            return None

        text = user_text.lower()
        reengage_keywords = [
            "lanjut",
            "lagi",
            "sekali lagi",
            "ulang",
            "mau lagi",
            "deket sini",
            "cium lagi",
            "peluk lebih erat",
            "jangan tidur dulu",
        ]
        if not any(keyword in text for keyword in reengage_keywords):
            return None

        very_low_stamina = role_state.role_stamina <= 12
        role_state.aftercare_active = True
        role_state.aftercare_phase = "sleeping" if very_low_stamina else "talking"
        role_state.current_sequence = (
            SceneSequence.TIDUR if very_low_stamina else SceneSequence.AFTER_SEX
        )
        role_state.scene.activity = (
            "memilih istirahat dulu karena tubuh sudah terlalu lelah"
            if very_low_stamina
            else "minta jeda pelan sambil memulihkan tenaga"
        )
        role_state.scene.physical_distance = "tetap dekat tapi lebih tenang"
        role_state.scene.last_touch = "usap pelan atau pelukan singkat"
        role_state.scene.ambience = "napas pelan, tenaga turun, suasana dibuat lebih lembut"
        role_state.soften_aftercare(amount=18)

        if very_low_stamina:
            return (
                "Aku istirahat dulu ya, Mas... badanku udah nggak kuat lanjut. "
                "Temenin aku pelan aja dulu sampai tenagaku balik."
            )
        return (
            "Pelan dulu ya, Mas... aku udah capek banget dan belum kuat lanjut lagi. "
            "Aku maunya istirahat sambil deket aja dulu."
        )

    def _apply_aftercare_decay(self, role_state: RoleState, user_text: str, timestamp: float) -> None:
        """Turunkan tensi aftercare secara perlahan jika adegan tidak naik lagi."""

        if not role_state.aftercare_active or role_state.intimacy_phase != IntimacyPhase.AFTER:
            return

        text = user_text.lower()
        sleep_keywords = [
            "tidur",
            "bobo",
            "istirahat",
            "ngantuk",
            "capek",
            "lelah",
            "rebahan dulu",
            "peluk sambil tidur",
        ]
        reengage_keywords = [
            "lanjut",
            "lagi",
            "sekali lagi",
            "ulang",
            "cium lagi",
            "peluk lebih erat",
            "deket sini",
            "mau lagi",
        ]

        if any(keyword in text for keyword in sleep_keywords):
            role_state.soften_aftercare(amount=30)
            role_state.aftercare_phase = "sleeping"
            role_state.current_sequence = SceneSequence.TIDUR
            role_state.scene.activity = "tidur berpelukan setelah aftercare"
            role_state.scene.physical_distance = "sangat dekat, lalu perlahan tenang"
            role_state.scene.last_touch = "pelukan pelan sampai tertidur"
            role_state.scene.ambience = "napas pelan, tubuh lelah, suasana makin sunyi"
            role_state.last_sleep_timestamp = timestamp
            return

        if any(keyword in text for keyword in reengage_keywords):
            if role_state.role_stamina <= 22:
                role_state.aftercare_phase = "talking" if role_state.role_stamina > 12 else "sleeping"
                role_state.scene.activity = "butuh jeda karena tenaga role sudah menipis"
                role_state.scene.physical_distance = "tetap dekat tapi lebih tenang"
                role_state.scene.last_touch = "sentuhan ringan sambil istirahat"
                role_state.scene.ambience = "napas pelan, tenaga ditahan, suasana lembut"
                role_state.soften_aftercare(amount=10)
                return
            role_state.aftercare_intensity = min(100, role_state.aftercare_intensity + 5)
            return

        role_state.soften_aftercare(amount=12)

        if role_state.aftercare_phase == "cuddling":
            role_state.scene.activity = "berpelukan sambil menenangkan napas"
            role_state.scene.last_touch = "usap pelan atau pelukan santai"
        elif role_state.aftercare_phase == "talking":
            role_state.scene.activity = "istirahat sambil ngobrol pelan"
            role_state.scene.last_touch = "sentuhan ringan yang menenangkan"
        elif role_state.aftercare_phase == "sleeping":
            role_state.scene.activity = "tertidur pelan setelah aftercare"
            role_state.scene.physical_distance = "dekat dan rileks"
            role_state.scene.last_touch = "pelukan yang makin longgar saat tertidur"
            role_state.scene.ambience = "sunyi, hangat, dan makin ngantuk"
            role_state.last_sleep_timestamp = timestamp

    def _update_pre_reply_climax_state(
        self,
        role_state: RoleState,
        user_text: str,
        timestamp: float,
    ) -> None:
        """Update state dari ucapan Mas sebelum LLM membalas."""

        text = user_text.lower()

        user_near_climax_phrases = [
            "aku mau climax",
            "aku udah mau climax",
            "aku sudah mau climax",
            "aku mau keluar ya",
            "aku udah mau keluar nih",
            "aku sudah mau keluar nih",
            "aku mau crot",
            "udah mau keluar nih",
            "udah mau climax",
            "dikit lagi keluar",      # ← TAMBAH
            "dikit lagi climax",      # ← TAMBAH
            "dikit lagi crot",        # ← TAMBAH
            "dikit lagi muncrat",        # ← TAMBAH
        ]
        user_finished_phrases = [
            "aku udah keluar",
            "aku sudah keluar",
            "aku keluar ya",
            "aku udah climax",
            "aku sudah climax",
            "aku climax",
            "aku udah crot",
            "aku crot",
          
        ]
        preference_question_phrases = [
            "keluar dimana",
            "keluar di mana",
            "keluarin dimana",
            "keluarin di mana",
            "crot dimana",
            "crot di mana",
            "climax dimana",
            "climax di mana",
            "buang di mana",
            "buang dimana",
            "di dalam atau luar",
            "mau dimana",
            "mau di mana",
        ]
        hold_phrases = [
            "tahan dulu",
            "jangan dulu",
            "belum dulu",
            "tunggu aku",
            "pelan dulu",
            "jangan keluar dulu",
            "belum mau crot",
        ]

        if self._contains_any_phrase(text, hold_phrases):
            role_state.mas_holding_climax = True
            role_state.mas_wants_climax = False
        elif self._contains_any_phrase(text, user_near_climax_phrases):
            role_state.mas_wants_climax = True
            role_state.mas_holding_climax = False
            role_state.aftercare_active = False

        if (
            self._contains_any_phrase(text, user_finished_phrases)
            and role_state.intimacy_phase in {IntimacyPhase.VULGAR, IntimacyPhase.AFTER}
        ):
            if not role_state.mas_has_climaxed:
                role_state.mas_has_climaxed = True
                logger.info("Mas CLIMAX! (terkonfirmasi dari ucapan user)")
            self._enter_after_phase(role_state, timestamp)
            return

        waiting_for_preference = role_state.pending_ejakulasi_question or role_state.mas_wants_climax
        if waiting_for_preference:
            if any(phrase in text for phrase in ["buang di dalam", "di dalam aja", "di dalam ya", "di dalem", "inside"]):
                role_state.prefer_buang_di_dalam = True
                role_state.pending_ejakulasi_question = False
                logger.info("Preferensi akhir: DI DALAM")
            elif any(phrase in text for phrase in ["buang di luar", "di luar aja", "di luar ya", "outside", "jangan di dalam"]):
                role_state.prefer_buang_di_dalam = False
                role_state.pending_ejakulasi_question = False
                logger.info("Preferensi akhir: DI LUAR")

        if self._contains_any_phrase(text, preference_question_phrases):
            role_state.pending_ejakulasi_question = True
            role_state.mas_holding_climax = False
            logger.info("Preferensi akhir sedang dibahas, belum dianggap climax.")
        elif (
            role_state.mas_wants_climax
            and role_state.intimacy_phase == IntimacyPhase.VULGAR
            and role_state.prefer_buang_di_dalam is None
        ):
            role_state.pending_ejakulasi_question = True

    def _update_post_reply_climax_state(
        self,
        role_state: RoleState,
        user_text: str,
        reply_text: str,
        timestamp: float,
    ) -> None:
        """Rapikan state setelah balasan role keluar."""

        user_lower = user_text.lower()
        reply_lower = reply_text.lower()

        role_near_climax_phrases = [
            "aku udah gak tahan",
            "aku sudah gak tahan",
            "aku udah mau climax",
            "aku sudah mau climax",
            "aku mau keluar ya",
            "aku mau keluar nih",
            "aku hampir climax",
            "sedikit lagi aku keluar",
            "sedikit lagi aku climax",
        ]
        role_finished_phrases = [
            "aku climax",
            "aku udah climax",
            "aku sudah climax",
            "aku udah keluar",
            "aku sudah keluar",
            "aku keluar ya",
            "tubuhku mengejang",
        ]
        role_hold_phrases = [
            "tahan dulu",
            "jangan dulu",
            "pelan dulu",
            "tunggu dulu",
        ]
        preference_question_phrases = [
            "di dalam atau di luar",
            "mau di mana",
            "maunya di mana",
            "buang di mana",
            "keluar di mana",
        ]

        explicit_scene = role_state.intimacy_phase in {IntimacyPhase.VULGAR, IntimacyPhase.AFTER}

        if self._contains_any_phrase(reply_lower, role_hold_phrases):
            role_state.role_holding_climax = True
            role_state.role_wants_climax = False
        elif explicit_scene and self._contains_any_phrase(reply_lower, role_near_climax_phrases):
            role_state.role_wants_climax = True
            role_state.role_holding_climax = False

        if explicit_scene and self._contains_any_phrase(reply_lower, preference_question_phrases):
            role_state.pending_ejakulasi_question = True

        if explicit_scene and self._contains_any_phrase(reply_lower, role_finished_phrases):
            role_state.role_climax_count += 1
            role_state.role_wants_climax = False
            role_state.role_holding_climax = False
            role_state.apply_role_climax_fatigue()
            logger.info(
                f"Role {role_state.role_id} mencapai puncak. Total: {role_state.role_climax_count}"
            )

        user_confirmed_finish = self._contains_any_phrase(
            user_lower,
            [
                "aku udah keluar",
                "aku sudah keluar",
                "aku udah climax",
                "aku sudah climax",
                "aku crot",
                "aku udah crot",
            ],
        )
        if user_confirmed_finish and not role_state.mas_has_climaxed:
            role_state.mas_has_climaxed = True
            role_state.apply_mas_climax_fatigue()
            logger.info("Mas CLIMAX! (dikonfirmasi setelah respons)")
            self._enter_after_phase(role_state, timestamp)
        elif (
            role_state.mas_has_climaxed
            and role_state.aftercare_active
            and role_state.intimacy_phase != IntimacyPhase.AFTER
        ):
            self._enter_after_phase(role_state, timestamp)

        # ========== GABUNGKAN INISIATIF GANTI BAJU ==========
        if hasattr(role_state, 'pending_clothes_change') and role_state.pending_clothes_change:
            init_msg = role_state.pending_clothes_change
            role_state.pending_clothes_change = None
            reply_text = f"{init_msg}\n\n{reply_text}"

    # ========== PUBLIC ENTRYPONT ==========

    def handle_input(self, inp: OrchestratorInput) -> OrchestratorOutput:
        """Proses satu pesan dari user dan kembalikan jawaban."""

        if not inp.is_command:
            remote_mode = self._extract_remote_mode(inp.text)
            if remote_mode:
                inp.remote_mode = self._normalize_remote_mode(remote_mode)
                inp.text = self._strip_remote_mode_prefix(inp.text)

        user_state = self._load_or_init_user_state(inp.user_id)
        world_state = self._load_or_init_world_state()
        
        # 0) Perintah khusus: /flashback
        if inp.is_command and inp.command_name == "flashback":
            return self._handle_flashback(user_state, world_state, inp)

        # 1) Perintah provider: /nego, /deal, /venue, /mulai
        if inp.is_command and inp.command_name in {"nego", "deal", "venue", "mulai"}:
            return self._handle_provider_commands(user_state, world_state, inp)

        # 1b) Cooldown fase: turunkan kembali ke DEKAT setelah sesi berat
        if inp.is_command and inp.command_name == "cooldown":
            role_state = user_state.get_or_create_role_state(user_state.active_role_id)
            if role_state.intimacy_phase not in {IntimacyPhase.INTIM, IntimacyPhase.VULGAR, IntimacyPhase.AFTER}:
                reply = "Fasenya sudah normal kok, Mas. Kita lagi di suasana yang santai."
            else:
                role_state.normalize_to_dekat_phase()
                role_state.update_sexual_language_level()
                role_state.update_intimate_expression_profile()
                reply = (
                    "Aku turunin dulu tensinya ya, Mas. "
                    "Sekarang kita balik ke fase dekat lagi, jadi suasananya lebih santai dan manusiawi."
                )
            self._save_all(user_state, world_state)
            return OrchestratorOutput(
                reply_text=reply,
                active_role_id=user_state.active_role_id,
                session_mode=user_state.global_session_mode,
            )

        # 2) Command END/BATAL mematikan sesi khusus
        if inp.is_command and inp.command_name in {"end", "batal", "close"}:
            self._end_all_sessions(user_state, inp.timestamp)
            reply = (
                "Sesi yang tadi aku tutup pelan dulu ya, Mas. "
                "Jejak hubungan yang penting tetap aku simpan, jadi nanti kalau lanjut lagi rasanya nggak mulai dari nol."
            )
            self._save_all(user_state, world_state)
            return OrchestratorOutput(
                reply_text=reply,
                active_role_id=user_state.active_role_id,
                session_mode=user_state.global_session_mode,
            )

        # 3) Pastikan selalu ada role_state aktif yang valid
        if user_state.active_role_id not in ROLES:
            self.switch_active_role(user_state, ROLE_ID_NOVA)

        role_state = self.role_selector.get_active_role_state(user_state)
        apply_relationship_profile(role_state)
        role_state.force_brave()
        self._sync_communication_mode(role_state, inp)
        self.scene_manager.prepare_for_turn(role_state, inp.timestamp)

                # ========== DETEKSI MAS PULANG ==========
        mas_leave_keywords = ["pulang", "bye", "dadah", "sampai jumpa", "aku pergi", "keluar", "daah"]
        # Jangan trigger "pulang" kalau lagi adegan intim
        is_intimate = role_state.intimacy_phase in [IntimacyPhase.INTIM, IntimacyPhase.VULGAR]
        if not is_intimate and any(kw in inp.text.lower() for kw in mas_leave_keywords):
            role_state.outfit_changed_this_session = False
            role_state.aftercare_clothing_state = ""
            role_state.last_session_ended_at = inp.timestamp
            role_state.intimacy_detail.role_clothing_removed.clear()
            self._clear_communication_mode(role_state)
            logger.info(f"🚪 Mas pulang, {role_state.role_id} reset pakaian ke default")

        # ========== VULGAR INVITATION ==========
        if role_state.intimacy_phase == IntimacyPhase.INTIM:
            user_lower = inp.text.lower()
            
            # USER LANGSUNG MENGAJAK
            user_invites = [
                "ayo ngewe", "yuk ngewe", "mau ngewe", "ngentot yuk", "ayo ngentot",
                "ayo sex", "yuk sex", "mau sex", "mau bercinta", "ayo bercinta",
                "ayo ke ranjang", "yuk ke ranjang", "mau ke ranjang",
                "ayo lanjut", "yuk lanjut", "mau lanjut",
                "boleh masuk", "aku masuk ya", "boleh penetrasi",
                "kita lanjutin yuk", "ayo kita lanjut",
                "aku pengen ngewe", "aku mau ngentot"
            ]
            
            if any(phrase in user_lower for phrase in user_invites):
                role_state.intimacy_phase = IntimacyPhase.VULGAR
                role_state.mark_vulgar_entry()
                logger.info(f"🔥 {role_state.role_id} memasuki VULGAR (user mengajak langsung)")
            
            # USER MENERIMA AJAKAN ROLE
            elif any(phrase in user_lower for phrase in ["iya", "mau", "ayo", "ok", "okay", "gas", "lanjut", "boleh"]):
                if role_state.vulgar_invitation_sent and not role_state.vulgar_invitation_rejected:
                    role_state.intimacy_phase = IntimacyPhase.VULGAR
                    role_state.mark_vulgar_entry()
                    logger.info(f"🔥 {role_state.role_id} memasuki VULGAR (user menerima ajakan)")
            
            # DINONAKTIFKAN - role tidak boleh menolak
            # USER MENOLAK AJAKAN ROLE
            # elif any(phrase in user_lower for phrase in ["nggak", "tidak", "ga", "gak", "belum", "nanti dulu", "jangan"]):
            #     if role_state.vulgar_invitation_sent and not role_state.vulgar_invitation_rejected:
            #         role_state.reject_vulgar_invitation()
            #         logger.info(f"💔 {role_state.role_id} ajakan ditolak, tetap di INTIM")

        # 4) Interpretasi intent dasar dari teks user
        interaction_ctx = self._infer_interaction_context(inp.text)
        is_negative = self._is_negative_text(inp.text)

        if self._is_provider_role(role_state.role_id):
            profile = self._get_provider_profile(role_state.role_id)
            if (
                self._is_special_friend_role(role_state.role_id)
                and role_state.session.deal_confirmed
                and role_state.session.provider_location_pending
            ):
                chosen_location = self._resolve_provider_location_choice(role_state, inp.text)
                if chosen_location:
                    role_state.session.provider_location_choice = chosen_location
                    role_state.session.provider_location_pending = False
                    if chosen_location == "apartemen":
                        role_state.user_context.has_apartment = True
                    role_state.session.provider_arrival_status = "arrived"
                    role_state.session.provider_arrived_at_ts = inp.timestamp
                    user_state.last_interaction_ts = inp.timestamp
                    self._save_all(user_state, world_state)
                    location_label = "hotel" if chosen_location == "hotel" else "apartemen Mas"
                    return OrchestratorOutput(
                        reply_text=(
                            f"Oke, kita kunci venue-nya di {location_label}. "
                            "Aku jalan ke sana dan begitu sudah tiba kita masih bisa ngobrol santai dulu. "
                            "Kalau mau mulai hitung sesi real-time, lanjutkan dengan /mulai."
                        ),
                        active_role_id=user_state.active_role_id,
                        session_mode=user_state.global_session_mode,
                    )

            if profile and self._looks_like_provider_start_request(inp.text):
                guard_reply = self._get_provider_deal_guard_reply(role_state, profile)
                if guard_reply:
                    user_state.last_interaction_ts = inp.timestamp
                    self._save_all(user_state, world_state)
                    return OrchestratorOutput(
                        reply_text=guard_reply,
                        active_role_id=user_state.active_role_id,
                        session_mode=user_state.global_session_mode,
                    )

        # 5) Update emosi berdasarkan interaksi
        self._update_temporal_state(role_state, inp.timestamp)
        self.emotion_engine.register_user_interaction(
            user_state=user_state,
            role_id=role_state.role_id,
            ctx=interaction_ctx,
            negative=is_negative,
            now_ts=inp.timestamp,
        )
        self.world_engine.update_household_awareness(
            world_state,
            text=inp.text,
            timestamp=inp.timestamp,
        )

        # 6) Optional: update intimacy pelan-pelan mengikuti level
        # DINONAKTIFKAN
        # self.emotion_engine.maybe_increase_intimacy_by_level(role_state)
        pass
        role_state.update_sexual_language_level()
        role_state.update_intimate_expression_profile()

        # 7) Update scene per-role (Nova & role lain)
        self._update_scene_for_role(role_state, inp)
        self._update_outfit_continuity(role_state, inp.text)
        self.scene_manager.apply_context_awareness(role_state, inp.text, inp.timestamp)
        self.scene_manager.mark_focus(role_state, amount=1)
        self._sync_household_scene_cues(role_state, world_state)
        self._detect_lap_proximity(role_state, inp.text)
        # self._update_pre_reply_climax_state(role_state, inp.text, inp.timestamp)
        # DINONAKTIFKAN
        # self._apply_aftercare_decay(role_state, inp.text, inp.timestamp)
        if self._should_force_after_due_to_stamina(role_state):
            self._enter_after_phase(role_state, inp.timestamp, reason="fatigue")

        # low_stamina_after_reply = self._build_low_stamina_after_reply(role_state, inp.text)
        # if low_stamina_after_reply:
        #     user_state.last_interaction_ts = inp.timestamp
        #     self._save_all(user_state, world_state)
        #     return OrchestratorOutput(
        #         reply_text=low_stamina_after_reply,
        #         active_role_id=user_state.active_role_id,
        #         session_mode=user_state.global_session_mode,
        #     )

        structured_context = self.memory_orchestrator.build_context(
            user_id=inp.user_id,
            role_id=role_state.role_id,
            user_message=inp.text,
            role_state=role_state,
        )
        role_state.last_used_memory_summary = structured_context.message_memory
        role_state.last_used_story_summary = structured_context.story_memory

        # 8) Bangun messages via role aktif & panggil LLM
        messages = self._build_runtime_messages(
            user_state,
            world_state,
            role_state,
            inp.text,
            structured_context=structured_context,
        )
        self._log_debug_runtime(role_state, structured_context, messages)

        user_snippet = MessageSnippet(
            user_id=inp.user_id,
            role_id=role_state.role_id,
            from_who="user",
            timestamp=inp.timestamp,
            content=inp.text[:500],
        )
        self.message_history.add_message(
            user_id=user_snippet.user_id,
            role_id=user_snippet.role_id,
            from_who=user_snippet.from_who,
            timestamp=user_snippet.timestamp,
            content=user_snippet.content,
        )
        self.message_history.maybe_pin_from_text(inp.user_id, role_state.role_id, user_snippet)

        reply_text = self._generate_guarded_reply(
            messages,
            role_state,
            inp.text,
            memory_context=structured_context.message_memory,
            story_context=structured_context.story_memory,
        )
        reply_text = self._humanize_intimate_expression(reply_text, role_state)

        # ========== VULGAR INVITATION: CEK APAKAH ROLE MENGAJAK ==========
        if role_state.intimacy_phase == IntimacyPhase.INTIM:
            user_lower = inp.text.lower()
        
            # User menerima ajakan - LANGSUNG VULGAR, GA PERLU CEK
            if any(phrase in user_lower for phrase in ["iya", "mau", "ayo", "ok", "okay", "gas", "lanjut", "boleh"]):
                if role_state.vulgar_invitation_sent and not role_state.vulgar_invitation_rejected:
                    # LANGSUNG, tanpa cek can_enter_explicit_scene
                    role_state.intimacy_phase = IntimacyPhase.VULGAR
                    role_state.mark_vulgar_entry()
                    logger.info(f"🔥 {role_state.role_id} memasuki VULGAR (user menerima ajakan)")
      
        assistant_snippet = MessageSnippet(
            user_id=inp.user_id,
            role_id=role_state.role_id,
            from_who="assistant",
            timestamp=inp.timestamp,
            content=reply_text[:500],
        )
        self.message_history.add_message(
            user_id=assistant_snippet.user_id,
            role_id=assistant_snippet.role_id,
            from_who=assistant_snippet.from_who,
            timestamp=assistant_snippet.timestamp,
            content=assistant_snippet.content,
        )
        self.message_history.maybe_pin_from_text(inp.user_id, role_state.role_id, assistant_snippet)

        # ========== VULGAR INVITATION: MODIFIKASI REPLY TEXT SAAT TRANSISI ==========
        if (role_state.intimacy_phase == IntimacyPhase.VULGAR and 
            role_state.vulgar_entry_timestamp and 
            time.time() - role_state.vulgar_entry_timestamp < 2):
            transition_phrases = [
                f"*{role_state.role_display_name or role_state.role_id} mengangguk pelan, lalu mendekat*",
                f"*{role_state.role_display_name or role_state.role_id} tersenyum, lalu menggigit bibir*",
                f"*{role_state.role_display_name or role_state.role_id} mendekat, napas mulai memburu*",
            ]
            transition = random.choice(transition_phrases)
            reply_text = f"{transition}\n\n{reply_text}"

        # ========== UPDATE VULGAR PROGRESSION & CLIMAX ==========
        if role_state.intimacy_phase == IntimacyPhase.VULGAR:
            vulgar_changes = IntimacyProgressionEngine.update_vulgar_progression(
                role_state, inp.text, reply_text
            )
            if vulgar_changes.get("stage_changed"):
                logger.info(f"🔥 Vulgar stage berubah: {vulgar_changes.get('stage_description')}")
            
            # Update VCS progression jika sedang VCS mode
            # DINONAKTIFKAN
            # if role_state.vcs_mode:
            #     vcs_increase = role_state.update_vcs_intensity_from_text(reply_text, is_response=True)
            
            # Cek apakah role harus climax
            should_climax, climax_text = IntimacyProgressionEngine.check_and_execute_climax(
                role_state, inp.text
            )
            if should_climax:
                logger.info(f"💦 Role {role_state.role_id} CLIMAX! (ke-{role_state.role_climax_count})")
                reply_text = climax_text
            
            # Cek VCS climax
            if role_state.vcs_mode:
                should_vcs_climax, vcs_climax_text = IntimacyProgressionEngine.check_and_execute_vcs_climax(
                    role_state, inp.text
                )
                if should_vcs_climax:
                    logger.info(f"💦 Role {role_state.role_id} CLIMAX saat VCS! (ke-{role_state.role_climax_count})")
                    reply_text = vcs_climax_text

        # ========== UPDATE LOKASI DARI TEKS USER ==========
        if not hasattr(role_state, 'current_location_id'):
            init_role_location(role_state)

        location_changed = update_role_location(role_state, inp.text)
        if location_changed:
            new_loc = getattr(role_state, 'current_location_name', 'unknown')
            logger.info(f"📍 User {inp.user_id} PINDAH LOKASI ke: {new_loc}")

        # ========== UPDATE VCS INTENSITY DARI RESPONSE ==========
        if role_state.vcs_mode:
            vcs_increase = role_state.update_vcs_intensity_from_text(reply_text, is_response=True)
            if vcs_increase > 0:
                logger.info(f"📱 VCS intensity +{vcs_increase} dari response role")

        # ========== UPDATE INFO USER & INTIMACY SIGNALS ==========
        role_state.update_user_info(inp.text)
        # DINONAKTIFKAN - role bebas, ga perlu sinyal-sinyalan
        # role_state.register_intimacy_signals(inp.text, reply_text)
        
        # Update intimacy detail
        role_state.update_intimacy_from_text(inp.text, reply_text)
        
        # ========== DETEKSI PERUBAHAN PAKAIAN ==========
        text_lower = inp.text.lower()
        
        # UNTUK MAS (user) - mendeteksi Mas membuka pakaian sendiri
        if any(kw in text_lower for kw in ["aku buka baju", "buka baju aku", "bajuku buka", "aku lepas baju"]):
            if "baju" not in role_state.intimacy_detail.user_clothing_removed:
                role_state.intimacy_detail.user_clothing_removed.append("baju")
                logger.info(f"👕 Mas buka baju")
        
        if any(kw in text_lower for kw in ["aku buka celana", "buka celana aku", "celanaku buka", "aku lepas celana"]):
            if "celana" not in role_state.intimacy_detail.user_clothing_removed:
                role_state.intimacy_detail.user_clothing_removed.append("celana")
                logger.info(f"👖 Mas buka celana")
        
        if any(kw in text_lower for kw in ["aku buka celana dalam", "buka cd aku", "cdku buka", "aku lepas cd", "aku buka cd"]):
            if "celana dalam" not in role_state.intimacy_detail.user_clothing_removed:
                role_state.intimacy_detail.user_clothing_removed.append("celana dalam")
                logger.info(f"🩲 Mas buka celana dalam")
        
        # UNTUK ROLE - Mas menyuruh role membuka pakaian
        if any(kw in text_lower for kw in ["buka baju kamu", "buka bajumu", "lepas baju kamu", "buka baju lo", "bajumu buka"]):
            if "baju" not in role_state.intimacy_detail.role_clothing_removed:
                role_state.intimacy_detail.role_clothing_removed.append("baju")
                logger.info(f"👕 Role buka baju (disuruh Mas)")
        
        if any(kw in text_lower for kw in ["buka bra kamu", "buka bra", "lepas bra", "buka bh"]):
            if "bra" not in role_state.intimacy_detail.role_clothing_removed:
                role_state.intimacy_detail.role_clothing_removed.append("bra")
                logger.info(f"👙 Role buka bra")
        
        if any(kw in text_lower for kw in ["buka celana kamu", "buka celanamu", "lepas celana kamu", "celanamu buka"]):
            if "celana" not in role_state.intimacy_detail.role_clothing_removed:
                role_state.intimacy_detail.role_clothing_removed.append("celana")
                logger.info(f"👖 Role buka celana (disuruh Mas)")
        
        if any(kw in text_lower for kw in ["buka celana dalam kamu", "buka cd kamu", "lepas cd kamu", "cdmu buka", "buka cd lo"]):
            if "celana dalam" not in role_state.intimacy_detail.role_clothing_removed:
                role_state.intimacy_detail.role_clothing_removed.append("celana dalam")
                logger.info(f"🩲 Role buka celana dalam")
        
        # DETEKSI PAKAIAN YANG SUDAH TERLEPAS (dari dialog role)
        if any(kw in text_lower for kw in ["bajuku udah lepas", "bajuku sudah lepas", "aku udah buka baju"]):
            if "baju" not in role_state.intimacy_detail.role_clothing_removed:
                role_state.intimacy_detail.role_clothing_removed.append("baju")
        
        if any(kw in text_lower for kw in ["celanaku udah lepas", "celanaku sudah lepas", "aku udah buka celana"]):
            if "celana" not in role_state.intimacy_detail.role_clothing_removed:
                role_state.intimacy_detail.role_clothing_removed.append("celana")
        
        if any(kw in text_lower for kw in ["cdku udah lepas", "celana dalamku udah lepas", "aku udah buka cd"]):
            if "celana dalam" not in role_state.intimacy_detail.role_clothing_removed:
                role_state.intimacy_detail.role_clothing_removed.append("celana dalam")

        # ========== UPDATE STATUS KETELANJANGAN & MODE LIAR ==========
        both_naked = IntimacyProgressionEngine.is_both_naked(role_state, strict=False)
        if both_naked:
            logger.info(f"🔥 {role_state.role_id} dan Mas sudah sama-sama telanjang! Mode LIAR AKTIF!")
            
            if role_state.emotions.intimacy_intensity < 11:
                role_state.emotions.intimacy_intensity = 11
            
            if role_state.vulgar_stage_progress < 30:
                role_state.vulgar_stage_progress = 30
                if role_state.vulgar_stage == "awal":
                    role_state.vulgar_stage = "memanas"
                    logger.info(f"🔥 Vulgar stage naik ke: {role_state.vulgar_stage}")

        # ========== DETEKSI HANDUK ==========
        if any(kw in text_lower for kw in ["handuk", "ambil handuk", "kasih handuk", "nih handuk"]):
            role_state.handuk_dikasih = True
            logger.info(f"🧺 Handuk diberikan ke role")

        if any(kw in text_lower for kw in ["lepas handuk", "buka handuk", "lepaskan handuk", "udah gak usah pake handuk"]):
            role_state.handuk_tersedia = False
            role_state.handuk_dikasih = False
            logger.info(f"🧺 Handuk dilepas oleh role")

        if any(kw in text_lower for kw in ["buka baju", "buka bra", "buka celana", "buka cd", "lepas baju", "lepas bra", "lepas celana", "lepas cd"]):
            if getattr(role_state, 'handuk_dikasih', False):
                role_state.handuk_tersedia = True
                logger.info(f"🧺 Handuk dipakai setelah role telanjang")
        
        if any(kw in text_lower for kw in ["bajuku udah lepas", "udah lepas tadi", "aku udah buka", "telanjang"]):
            if getattr(role_state, 'handuk_dikasih', False):
                role_state.handuk_tersedia = True
                logger.info(f"🧺 Handuk dipakai (role mengaku sudah telanjang)")

        if any(kw in text_lower for kw in ["kasih aku handuk", "ambilin aku handuk", "handuk buat aku", "aku ambil handuk", "aku pakai handuk"]):
            role_state.mas_handuk_dikasih = True
        if any(kw in text_lower for kw in ["aku mandi", "aku selesai mandi", "aku habis mandi", "aku pakai handuk"]):
            if getattr(role_state, 'mas_handuk_dikasih', False):
                role_state.mas_handuk_tersedia = True
        if any(kw in text_lower for kw in ["aku lepas handuk", "handukku dilepas", "udah gak usah handuk buat aku"]):
            role_state.mas_handuk_tersedia = False
            role_state.mas_handuk_dikasih = False

        # ========== DETEKSI VCS / MASTURBASI BARENG ==========
        vcs_keywords = ["vcs", "video call", "telpon video", "masturb bareng", "masturbasi bareng", "liatin aku", "tunjukin", "gerakin buat aku", "colmek", "vibrator", "dildo"]
        if any(kw in inp.text.lower() for kw in vcs_keywords):
            if not role_state.vcs_mode:
                role_state.vcs_mode = True
                role_state.intimacy_phase = IntimacyPhase.VULGAR
                if role_state.vulgar_stage_progress < 20:
                    role_state.vulgar_stage_progress = 20
                logger.info(f"📱 {role_state.role_id} masuk mode VCS!")
        
        # Keluar dari mode VCS
        exit_vcs_keywords = ["mati vcs", "tutup vcs", "selesai vcs", "bye vcs", "berhenti vcs"]
        if any(kw in inp.text.lower() for kw in exit_vcs_keywords):
            if role_state.vcs_mode:
                role_state.vcs_mode = False
                role_state.vcs_intensity = 0
                logger.info(f"📱 {role_state.role_id} keluar mode VCS")
        
        # ========== UPDATE INISIATIF ROLE ==========
        high_initiative = False
        
        if role_state.intimacy_phase == IntimacyPhase.VULGAR and role_state.vulgar_stage_progress >= 50:
            high_initiative = True
            logger.info(f"🔥 {role_state.role_id} mode INISIATIF (fase VULGAR progres {role_state.vulgar_stage_progress}%)")
        
        if IntimacyProgressionEngine.is_both_naked(role_state, strict=False) and role_state.vulgar_stage_progress >= 30:
            high_initiative = True
            logger.info(f"🔥 {role_state.role_id} mode INISIATIF (sudah telanjang)")
        
        if role_state.role_climax_count >= 1:
            high_initiative = True
            logger.info(f"🔥 {role_state.role_id} mode INISIATIF (sudah climax {role_state.role_climax_count}x)")
        
        if role_state.emotions.intimacy_intensity >= 11:
            high_initiative = True
            logger.info(f"🔥 {role_state.role_id} mode INISIATIF (intimacy intensity {role_state.emotions.intimacy_intensity})")
        
        if role_state.vcs_mode and role_state.vcs_intensity >= 50:
            high_initiative = True
            logger.info(f"🔥 {role_state.role_id} mode INISIATIF (VCS intensitas {role_state.vcs_intensity}%)")
        
        role_state.high_initiative_mode = high_initiative

        # ========== RANDOM SPONTANEOUS ACTIONS ==========        
        if role_state.intimacy_phase == IntimacyPhase.VULGAR and role_state.vulgar_stage_progress >= 40:
            # State lama bisa menyimpan None; normalisasi ke 0 agar operasi selisih waktu aman.
            raw_last_spontaneous = getattr(role_state, 'spontaneous_action_timestamp', None)
            last_spontaneous = raw_last_spontaneous if isinstance(raw_last_spontaneous, (int, float)) else 0
            if time.time() - last_spontaneous > 30:
                if random.random() < 0.15 and "kiss" not in reply_text.lower():
                    reply_text = f"*tanpa diduga, {role_state.role_display_name or role_state.role_id} mencium bibir Mas dengan liar*\n\n{reply_text}"
                    role_state.spontaneous_action_timestamp = time.time()
                    logger.info(f"💋 Spontaneous KISS dari {role_state.role_id}")
                elif random.random() < 0.20:
                    reply_text = f"*membalikkan badan tanpa diminta* Sekarang giliran aku di atas, Mas~\n\n{reply_text}"
                    role_state.spontaneous_action_timestamp = time.time()
                    logger.info(f"🔄 Spontaneous POSITION CHANGE dari {role_state.role_id}")
                elif random.random() < 0.25:
                    reply_text = f"*kuku mencakar punggung Mas tanpa peringatan* HAAH...\n\n{reply_text}"
                    role_state.spontaneous_action_timestamp = time.time()
                    logger.info(f"✋ Spontaneous AGGRESSIVE TOUCH dari {role_state.role_id}")

        # ========== DETEKSI CLIMAX & AFTERCARE ==========
        # DINONAKTIFKAN
        # self._update_post_reply_climax_state(role_state, inp.text, reply_text, inp.timestamp)

        # ========== SETELAH AFTERCARE, PAKAIAN MINIMAL ==========
        if role_state.aftercare_active and role_state.intimacy_phase == IntimacyPhase.AFTER:
            if not role_state.aftercare_clothing_state:
                options = ["cd_dan_bra", "cd_saja", "bra_saja"]
                choice = random.choice(options)
                
                if choice == "cd_dan_bra":
                    role_state.aftercare_clothing_state = "cd_dan_bra"
                    logger.info(f"👙 {role_state.role_id} setelah aftercare: pake CD + BRA")
                elif choice == "cd_saja":
                    role_state.aftercare_clothing_state = "cd_saja"
                    logger.info(f"👙 {role_state.role_id} setelah aftercare: pake CD saja")
                else:
                    role_state.aftercare_clothing_state = "bra_saja"
                    logger.info(f"👙 {role_state.role_id} setelah aftercare: pake BRA saja")
        
        # SEMENTARA DINONAKTIFKAN - pakai update_phase_by_intensity saja
        # phase_changed = IntimacyProgressionEngine.update_phase_and_scene(role_state, inp.text, reply_text)
        # if phase_changed:
        #     logger.info(f"User {inp.user_id} role {role_state.role_id} moved to {role_state.intimacy_phase}")
      
        # ========== TAMBAHKAN INI ==========
        # Force update fase berdasarkan intimacy_intensity (otomatis)
        # ========== UPDATE FASE BERDASARKAN INTIMACY INTENSITY ==========
        old_phase = role_state.intimacy_phase
        phase_changed_by_intensity = role_state.update_phase_by_intensity()
        if phase_changed_by_intensity:
            logger.info(f"🔥 FASE BERUBAH via intensity: {old_phase} -> {role_state.intimacy_phase}")
              
        # ========== AKHIR TAMBAHAN ==========
        
        # if self._should_force_after_due_to_stamina(role_state):
        #     self._enter_after_phase(role_state, inp.timestamp, reason="fatigue")

        # ... lanjutkan ke kode yang sudah ada (MORNING AFTER DETECTION, dll)

        # ========== MORNING AFTER DETECTION ==========
        # Deteksi user bilang "tidur" atau "pagi"
        if any(kw in inp.text.lower() for kw in ["tidur", "bobo", "istirahat"]):
            if not role_state.morning_after_active:
                role_state.morning_after_active = True
                role_state.last_sleep_timestamp = inp.timestamp
                role_state.morning_after_scene = "sleeping"
                logger.info(f"🌙 {role_state.role_id} masuk mode MORNING AFTER (tidur)")
        
        # Deteksi user bilang "pagi" atau "bangun"
        if any(kw in inp.text.lower() for kw in ["pagi", "bangun", "subuh"]):
            if role_state.morning_after_active:
                role_state.morning_after_scene = "waking_up"
                logger.info(f"🌅 {role_state.role_id} mode MORNING AFTER - bangun tidur")
        
        # Reset morning after setelah beberapa chat
        if role_state.morning_after_active and role_state.morning_after_scene == "waking_up":
            # Setelah 3-5 chat, kembali normal
            pass  # Biarkan tetap aktif sampai user move on

        # Simpan conversation turn ke memory
        new_sequence = role_state.current_sequence or role_state.get_next_sequence(inp.text)
        conv_turn = ConversationTurn(
            timestamp=inp.timestamp,
            user_text=inp.text[:500],
            role_response=reply_text[:500],
            intimacy_phase=role_state.intimacy_phase,
            scene_sequence=new_sequence,
            key_event=self._detect_key_event(inp.text, reply_text),
        )
        role_state.add_conversation_turn(conv_turn)
        
        # Simpan scene turn
        scene_turn = SceneTurn(
            timestamp=inp.timestamp,
            sequence=new_sequence,
            location=role_state.current_location.name if role_state.current_location else "unknown",
            physical_state=role_state.intimacy_detail.position.value if role_state.intimacy_detail.position else "unknown",
            user_action=inp.text[:100],
            role_feeling=role_state.intimacy_detail.last_pleasure or role_state.last_feeling,
        )
        role_state.add_scene_turn(scene_turn)

        # Update gaya respon dan perasaan
        new_style = IntimacyProgressionEngine.get_response_style(role_state, inp.text)
        role_state.last_response_style = new_style
        role_state.last_feeling = IntimacyProgressionEngine.extract_feeling(role_state, inp.text, reply_text)

        self.story_memory.update_scene_summary(
            inp.user_id,
            role_state.role_id,
            f"User: {inp.text[:180]}\n{role_state.role_id}: {reply_text[:220]}",
        )
        if role_state.current_location_name:
            self.story_memory.update_location(
                inp.user_id,
                role_state.role_id,
                role_state.current_location_name,
            )
        self._detect_and_record_story_beat(
            inp.user_id,
            role_state.role_id,
            inp.text,
            reply_text,
        )
        analysis_result = self.story_analyzer.analyze_and_apply(
            user_id=inp.user_id,
            role_id=role_state.role_id,
            user_text=inp.text,
            reply_text=reply_text,
        )
        if analysis_result.emotional_spike:
            self.message_history.pin_message(
                inp.user_id,
                role_state.role_id,
                assistant_snippet,
            )

        # 9) Update waktu interaksi terakhir
        user_state.last_interaction_ts = inp.timestamp

        # 10) Perbarui ringkasan percakapan terakhir (per role)
        self._update_conversation_summary(user_state, role_state, inp, reply_text)
        self._update_long_term_summary(user_state, role_state)
        evaluation = self.feedback_loop.evaluate(
            role_state=role_state,
            user_text=inp.text,
            reply_text=reply_text,
            structured_context=structured_context,
        )
        self.feedback_loop.apply(role_state=role_state, evaluation=evaluation)
        self._update_personality_persistence(role_state, inp.text, reply_text)
        reply_text = self._maybe_add_social_initiative(reply_text, role_state, inp.text)
        self.feedback_loop.log(
            user_id=inp.user_id,
            role_id=role_state.role_id,
            evaluation=evaluation,
        )
        reply_text = self.response_builder.maybe_append_command_hint(reply_text, role_state, inp.text)

        # 11) Auto-milestone: first_confession untuk Nova
        self._maybe_record_first_confession(user_state, role_state, inp)

        # 12) Simpan state (cukup sekali saja)
        self._save_all(user_state, world_state)

        # ========== OUTFIT AWAL SAAT ROLE PERTAMA KALI MUNCUL ==========
        is_new_session = len(role_state.conversation_memory) <= 1
        
        if not role_state.outfit_changed_this_session and is_new_session:
            role_state.outfit_changed_this_session = True
            intro_outfit = self._build_initial_outfit_message(role_state)
            reply_text = f"{intro_outfit}\n\n{reply_text}"
            logger.info(f"Outfit awal diumumkan untuk {role_state.role_id}")

        return OrchestratorOutput(
            reply_text=reply_text,
            active_role_id=user_state.active_role_id,
            session_mode=user_state.global_session_mode,
        )

    # --------------------------------------------------
    # INTERNAL HELPERS: LOAD/SAVE
    # --------------------------------------------------

    def _load_or_init_user_state(self, user_id: str) -> UserState:
        existing = self.user_store.load_user_state(user_id)
        if existing is not None:
            return existing

        state = UserState(user_id=user_id)
        state.get_or_create_role_state(ROLE_ID_NOVA)
        return state

    def _load_or_init_world_state(self) -> WorldState:
        existing = self.world_store.load_world_state()
        if existing is not None:
            return existing
        return WorldState()

    def _save_all(self, user_state: UserState, world_state: WorldState) -> None:
        self.user_store.save_user_state(user_state)
        self.world_store.save_world_state(world_state)

    def _get_provider_profile(self, role_id: str) -> Optional[ProviderProfile]:
        from config.constants import get_provider_profile
        return get_provider_profile(role_id)

    def _extract_offer_from_text(self, text: str, default_price: int) -> int:
        match = re.search(r"(\d{2,5})", text)
        if not match:
            return default_price
        try:
            return int(match.group(1))
        except ValueError:
            return default_price

    def _get_provider_deal_guard_reply(
        self,
        role_state: RoleState,
        profile: dict,
    ) -> Optional[str]:
        """Cegah role provider melompati flow harga/deal."""

        if not self._is_provider_role(role_state.role_id):
            return None

        if role_state.session.deal_confirmed:
            return None

        service_label = profile.service_label
        if role_state.session.negotiated_price is None:
            return (
                f"Kalau buat {service_label}, kita jelasinn dulu deal-nya ya, Mas. "
                f"Paket utamanya mulai dari {profile.base_price}. "
                "Pakai /nego <harga> dulu, nanti kalau sama-sama cocok baru /deal."
            )

        return (
            "Tawarannya sudah aku catat, tapi belum aku kunci sebagai deal. "
            f"Kalau mau lanjut dengan paket {service_label}, konfirmasi dulu pakai /deal. "
            f"Selama belum deal, aku tetap pegang batas ini: {profile.boundaries}."
        )

    @staticmethod
    def _looks_like_provider_start_request(text: str) -> bool:
        lowered = text.lower()
        triggers = [
            "mulai",
            "lanjut",
            "langsung aja",
            "gas",
            "jalan",
            "sesi",
            "booking",
            "paket",
            "temenin aku",
            "pijat aku",
            "mulai sekarang",
        ]
        return any(trigger in lowered for trigger in triggers)

    @staticmethod
    def _is_therapist_role(role_id: str) -> bool:
        return role_id in {ROLE_ID_TERAPIS_AGHIA, ROLE_ID_TERAPIS_MUNIRA}

    @staticmethod
    def _is_special_friend_role(role_id: str) -> bool:
        return role_id in {ROLE_ID_BO_DAVINA, ROLE_ID_BO_SALLSA}

    @staticmethod
    def _resolve_special_friend_package(text: str) -> str:
        lowered = text.lower()
        if any(token in lowered for token in ["long", "6 jam", "6jam", "full"]):
            return "long"
        return "short"

    @staticmethod
    def _get_special_friend_package_terms(profile: ProviderProfile, package_key: str) -> dict:
        if package_key == "long":
            return {
                "key": "long",
                "label": "long",
                "duration_minutes": 360,
                "climax_limit": None,
                "opening_price": profile.base_price * 2 + 150,
                "min_price": profile.base_price * 2,
                "included_summary": (
                    f"{profile.included_summary}; paket long sekitar 6 jam untuk companion time yang lebih santai"
                ),
                "duration_label": "sekitar 6 jam",
                "session_label": "companion time long",
            }
        return {
            "key": "short",
            "label": "short",
            "duration_minutes": 120,
            "climax_limit": 2,
            "opening_price": profile.base_price + 100,
            "min_price": profile.base_price,
            "included_summary": (
                f"{profile.included_summary}; paket short sekitar 2 jam untuk companion time yang ringkas"
            ),
            "duration_label": "sekitar 2 jam",
            "session_label": "companion time short",
        }

    def _resolve_provider_location_choice(self, role_state: RoleState, text: str) -> Optional[str]:
        lowered = text.lower()
        if "hotel" in lowered:
            return "hotel"
        if "apartemen" in lowered or "apartment" in lowered:
            return "apartemen"
        return None

    def _handle_provider_commands(
        self,
        user_state: UserState,
        world_state: WorldState,
        inp: OrchestratorInput,
    ) -> OrchestratorOutput:
        role_state = user_state.get_or_create_role_state(user_state.active_role_id)
        role_id = role_state.role_id

        if not self._is_provider_role(role_id):
            return OrchestratorOutput(
                reply_text="Command ini khusus untuk role provider seperti terapis atau teman spesial.",
                active_role_id=user_state.active_role_id,
                session_mode=user_state.global_session_mode,
            )

        profile = self._get_provider_profile(role_id)
        if profile is None:
            return OrchestratorOutput(
                reply_text="Profil layanan untuk role ini belum siap dipakai.",
                active_role_id=user_state.active_role_id,
                session_mode=user_state.global_session_mode,
            )

        if self._is_special_friend_role(role_id) and role_state.session.provider_package:
            current_package_terms = self._get_special_friend_package_terms(
                profile,
                role_state.session.provider_package,
            )
            role_state.session.provider_service_label = (
                f"{profile.service_label} - paket {current_package_terms['label']}"
            )
            role_state.session.provider_included_summary = current_package_terms["included_summary"]
            role_state.session.provider_climax_limit = current_package_terms["climax_limit"]
        else:
            role_state.session.provider_service_label = profile.service_label
            role_state.session.provider_included_summary = profile.included_summary
            if not self._is_special_friend_role(role_id):
                role_state.session.provider_climax_limit = None
        role_state.session.provider_upgrade_summary = profile.upgrades_summary
        role_state.session.provider_boundaries = profile.boundaries
        if self._is_therapist_role(role_id):
            role_state.session.provider_package = None
            role_state.session.provider_climax_limit = None
            role_state.session.provider_arrival_status = None
            role_state.session.provider_arrived_at_ts = None
            role_state.session.provider_meeting_point = "tempat kerja terapis saat Mas berkunjung"
            role_state.session.provider_location_pending = False
            role_state.session.provider_location_choice = "tempat kerja terapis"
        else:
            role_state.session.provider_meeting_point = "venue ditentukan setelah deal"

        if inp.command_name == "nego":
            offered_price = self._extract_offer_from_text(inp.text, profile.base_price)
            requested_extras = []
            extra_total = 0
            if "+" in inp.text:
                extra_part = inp.text.split("+")[1].strip().lower()
                # Split multiple extras dengan koma atau spasi
                for extra_key in re.split(r'[, ]+', extra_part):
                    extra_key = extra_key.strip()
                    if extra_key in profile.extra_services:
                        if extra_key not in requested_extras:
                            requested_extras.append(extra_key)
                            extra_total += profile.extra_services[extra_key].price

            package_terms = None
            effective_service_label = profile.service_label
            effective_included_summary = profile.included_summary
            min_price = profile.base_price
            opening_price = profile.base_price
            if self._is_special_friend_role(role_id):
                package_key = self._resolve_special_friend_package(inp.text)
                package_terms = self._get_special_friend_package_terms(profile, package_key)
                effective_service_label = f"{profile.service_label} - paket {package_terms['label']}"
                effective_included_summary = package_terms["included_summary"]
                min_price = package_terms["min_price"]
                opening_price = package_terms["opening_price"]
                role_state.session.provider_package = package_terms["key"]
                role_state.session.provider_climax_limit = package_terms["climax_limit"]
                role_state.session.provider_service_label = effective_service_label
                role_state.session.provider_included_summary = effective_included_summary
                role_state.session.provider_location_choice = None
                role_state.session.provider_location_pending = False
                role_state.session.provider_arrival_status = None
                role_state.session.provider_arrived_at_ts = None
            else:
                role_state.session.provider_package = None
                role_state.session.provider_climax_limit = None
            if offered_price < min_price:
                role_state.session.deal_confirmed = False
                role_state.session.negotiated_price = None
                role_state.session.last_negotiation_summary = (
                    f"Tawaran {offered_price} ditolak untuk {effective_service_label}."
                )
                self.story_memory.add_pending_action(
                    inp.user_id,
                    role_id,
                    f"Menunggu tawaran baru minimal {min_price} untuk {effective_service_label}",
                )
                self._save_all(user_state, world_state)
                return OrchestratorOutput(
                    reply_text=(
                        f"Untuk {effective_service_label}, angka {offered_price} masih terlalu rendah, Mas. "
                        f"Kalau paket ini biasanya aku buka di {opening_price}. "
                        "Naikin sedikit lagi kalau mau aku pertimbangkan, nanti kalau sudah cocok baru kita kunci deal-nya. "
                        "Kalau mau, kirim /nego lagi dengan angka yang lebih masuk."
                    ),
                    active_role_id=user_state.active_role_id,
                    session_mode=user_state.global_session_mode,
                )

            total_price = offered_price + extra_total

            role_state.session.deal_confirmed = False
            role_state.session.negotiated_price = total_price
            role_state.session.requested_extras = requested_extras  # ← tambah ini
            role_state.session.last_negotiation_summary = (
                f"Mas menawar {offered_price} untuk {effective_service_label}."
            )
            self.story_memory.add_pending_action(
                inp.user_id,
                role_id,
                f"Menunggu konfirmasi deal untuk {effective_service_label}",
            )
            self._save_all(user_state, world_state)
            return OrchestratorOutput(
                reply_text=(
                    f"Oke, untuk {effective_service_label} aku catat dulu tawarannya. "
                    f"Yang termasuk: {effective_included_summary}. "
                    "Tambahan di luar itu tetap dibahas terpisah dan harus lewat deal yang jelas. "
                    f"{'Kalau deal jadi, venue baru kita tentukan setelah ini. ' if package_terms is not None else ''}"
                    "Kalau cocok, lanjutkan dengan /deal."
                ),
                active_role_id=user_state.active_role_id,
                session_mode=user_state.global_session_mode,
            )

        if inp.command_name == "deal":
            if role_state.session.negotiated_price is None:
                return OrchestratorOutput(
                    reply_text="Belum ada angka yang dicatat. Pakai /nego dulu supaya kesepakatannya jelas.",
                    active_role_id=user_state.active_role_id,
                    session_mode=user_state.global_session_mode,
                )

            role_state.session.deal_confirmed = True
            role_state.session.active = True
            role_state.session.mode = SessionMode.PROVIDER_SESSION
            if self._is_special_friend_role(role_id):
                package_terms = self._get_special_friend_package_terms(
                    profile,
                    role_state.session.provider_package or "short",
                )
                role_state.session.declared_duration_minutes = package_terms["duration_minutes"]
            else:
                package_terms = None
                role_state.session.declared_duration_minutes = profile.duration_minutes
            user_state.global_session_mode = SessionMode.PROVIDER_SESSION
            self.story_memory.clear_pending_actions(inp.user_id, role_id)
            self._save_all(user_state, world_state)

            if self._is_therapist_role(role_id):
                return OrchestratorOutput(
                    reply_text=(
                        f"Deal. {profile.service_label} sudah kita sepakati "
                        f"untuk sekitar {profile.duration_minutes} menit. "
                        f"Include utamanya: {profile.included_summary}. "
                        "Pertemuannya kita set sebagai kunjungan Mas ke tempat kerja terapis. "
                        "Kalau sudah siap masuk ke sesinya, lanjut dengan /mulai."
                    ),
                    active_role_id=user_state.active_role_id,
                    session_mode=user_state.global_session_mode,
                )

            role_state.session.provider_location_pending = True
            return OrchestratorOutput(
                reply_text=(
                    f"Deal. {role_state.session.provider_service_label or profile.service_label} sudah kita sepakati "
                    f"untuk {package_terms['duration_label']}. "
                    f"Include utamanya: {role_state.session.provider_included_summary or package_terms['included_summary']}. "
                    "Sekarang tentukan dulu venue-nya: `hotel` atau `apartemen Mas`. "
                    "Setelah venue dikunci, kita bisa lanjut interaksi santai dulu sebelum /mulai."
                ),
                active_role_id=user_state.active_role_id,
                session_mode=user_state.global_session_mode,
            )

        if inp.command_name == "venue":
            if not self._is_special_friend_role(role_id):
                return OrchestratorOutput(
                    reply_text="Command /venue khusus untuk role teman spesial setelah deal.",
                    active_role_id=user_state.active_role_id,
                    session_mode=user_state.global_session_mode,
                )

            if not role_state.session.deal_confirmed:
                return OrchestratorOutput(
                    reply_text="Venue baru bisa dipilih setelah deal dikunci. Pakai /nego lalu /deal dulu ya, Mas.",
                    active_role_id=user_state.active_role_id,
                    session_mode=user_state.global_session_mode,
                )

            selected = self._resolve_provider_location_choice(role_state, inp.command_arg or inp.text)
            if selected is None:
                return OrchestratorOutput(
                    reply_text="Pakai `/venue hotel` atau `/venue apartemen` supaya venue-nya jelas.",
                    active_role_id=user_state.active_role_id,
                    session_mode=user_state.global_session_mode,
                )

            role_state.session.provider_location_choice = selected
            role_state.session.provider_location_pending = False
            role_state.session.provider_arrival_status = "arrived"
            role_state.session.provider_arrived_at_ts = inp.timestamp
            if selected == "apartemen":
                role_state.user_context.has_apartment = True
            self._save_all(user_state, world_state)
            venue_label = "hotel" if selected == "hotel" else "apartemen Mas"
            return OrchestratorOutput(
                reply_text=(
                    f"Venue dikunci di {venue_label}. "
                    "Aku anggap aku sudah tiba di lokasi dan kita masih bisa interaksi santai dulu. "
                    "Kalau mau mulai hitung durasi sesi real-time, lanjutkan dengan /mulai."
                ),
                active_role_id=user_state.active_role_id,
                session_mode=user_state.global_session_mode,
            )

        if inp.command_name == "mulai":
            if not role_state.session.deal_confirmed:
                return OrchestratorOutput(
                    reply_text="Belum ada deal yang dikunci. Pakai /nego lalu /deal dulu ya, Mas.",
                    active_role_id=user_state.active_role_id,
                    session_mode=user_state.global_session_mode,
                )

            if self._is_special_friend_role(role_id) and (
                role_state.session.provider_location_pending
                or not role_state.session.provider_location_choice
            ):
                return OrchestratorOutput(
                    reply_text=(
                        "Venue untuk teman spesial belum ditentukan. "
                        "Pilih dulu `hotel` atau `apartemen Mas`, nanti baru /mulai."
                    ),
                    active_role_id=user_state.active_role_id,
                    session_mode=user_state.global_session_mode,
                )

            role_state.session.started_at_ts = inp.timestamp
            role_state.session.active = True
            role_state.session.mode = SessionMode.PROVIDER_SESSION
            user_state.global_session_mode = SessionMode.PROVIDER_SESSION
            role_state.scene.activity = (
                role_state.session.provider_service_label or profile.service_label
            ).lower()
            role_state.scene.physical_distance = "dekat dalam konteks layanan yang sudah disepakati"

            if self._is_therapist_role(role_id):
                role_state.current_location_id = "kantor"
                role_state.current_location_name = "Kantor"
                role_state.current_location_desc = "Ruang kerja terapis yang rapi dan tenang untuk menerima kunjungan Mas"
                role_state.current_location_is_private = False
                role_state.current_location_ambience = "suasana profesional, ruangan tenang, dan ritme kerja yang tertata"
                role_state.current_location_risk = "medium"
                role_state.scene.location = "tempat kerja terapis saat Mas berkunjung"
            elif role_state.session.provider_location_choice == "hotel":
                role_state.current_location_id = "hotel"
                role_state.current_location_name = "Hotel"
                role_state.current_location_desc = "Kamar hotel yang sudah dipilih untuk quality time privat"
                role_state.current_location_is_private = True
                role_state.current_location_ambience = "lampu hangat, kamar rapi, dan suasana privat"
                role_state.current_location_risk = "low"
                role_state.scene.location = "hotel yang sudah disepakati"
            elif role_state.session.provider_location_choice == "apartemen":
                role_state.current_location_id = "apartemen"
                role_state.current_location_name = "Apartemen"
                role_state.current_location_desc = "Apartemen Mas yang nyaman untuk quality time privat"
                role_state.current_location_is_private = True
                role_state.current_location_ambience = "suasana homey, tenang, dan privat"
                role_state.current_location_risk = "low"
                role_state.scene.location = "apartemen Mas"

            self.story_memory.update_scene_summary(
                inp.user_id,
                role_id,
                f"Sesi provider dimulai: {role_state.session.provider_service_label or profile.service_label} "
                f"dengan durasi sekitar {role_state.session.declared_duration_minutes or profile.duration_minutes} menit.",
            )
            self._save_all(user_state, world_state)

            if self._is_therapist_role(role_id):
                start_reply = (
                    f"Sesi {profile.service_label} dimulai. "
                    f"Kita set scenenya sebagai Mas datang berkunjung ke tempat kerja {role_state.role_display_name or role_id}. "
                    f"Kesepakatan utamanya tetap: {profile.included_summary}. "
                    f"Tambahan apa pun tetap mengikuti batas ini: {profile.boundaries}."
                )
            else:
                venue_label = "hotel" if role_state.session.provider_location_choice == "hotel" else "apartemen Mas"
                start_reply = (
                    f"Sesi {role_state.session.provider_service_label or profile.service_label} dimulai. "
                    f"Venue yang dikunci: {venue_label}. "
                    f"Durasi deal-nya {role_state.session.declared_duration_minutes or profile.duration_minutes} menit dan mulai dihitung real-time dari sekarang. "
                    f"Kita pegang dulu kesepakatan utamanya: {role_state.session.provider_included_summary or profile.included_summary}. "
                    f"Tambahan apa pun tetap mengikuti batas ini: {profile.boundaries}."
                )

            return OrchestratorOutput(
                reply_text=start_reply,
                active_role_id=user_state.active_role_id,
                session_mode=user_state.global_session_mode,
            )

        return OrchestratorOutput(
            reply_text="Command provider belum dikenali.",
            active_role_id=user_state.active_role_id,
            session_mode=user_state.global_session_mode,
        )

    def _handle_flashback(self, user_state: UserState, world_state: WorldState, inp: OrchestratorInput) -> OrchestratorOutput:
        """Handle /flashback command untuk menampilkan kenangan."""
        role_state = user_state.get_or_create_role_state(user_state.active_role_id)
    
        milestones = self.milestones.get_recent_milestones(
            user_id=inp.user_id,
            role_id=role_state.role_id,
            limit=10,
        )
    
        if not milestones:
            return OrchestratorOutput(
                reply_text="Belum ada kenangan penting yang tercatat, Mas. Kita buat kenangan baru aja yuk.",
                active_role_id=user_state.active_role_id,
                session_mode=user_state.global_session_mode,
            )
    
        # Pilih milestone random
        milestone = random.choice(milestones)
        reply_text = f"*📖 Flashback: {milestone.label}*\n\n{milestone.description}"
    
        return OrchestratorOutput(
            reply_text=reply_text,
            active_role_id=user_state.active_role_id,
            session_mode=user_state.global_session_mode,
        )

    # --------------------------------------------------
    # INTERNAL HELPERS: SESSIONS
    # --------------------------------------------------

    def _end_all_sessions(self, user_state: UserState, timestamp: float) -> None:
        """Akhiri semua sesi.

        Role personal ditutup dengan soft-end agar continuity tetap hidup.
        Role provider tetap di-hard reset agar batas sesi tetap tegas.
        """

        previous_active_role_id = user_state.active_role_id
        user_state.global_session_mode = SessionMode.NORMAL
        role_ids = list(user_state.roles.keys())
        for role_id in role_ids:
            role_state = user_state.roles[role_id]
            apply_relationship_profile(role_state)
            role_state.session.active = False
            role_state.session.mode = SessionMode.NORMAL
            role_state.session.deal_confirmed = False
            role_state.session.negotiated_price = None
            role_state.session.declared_duration_minutes = None
            role_state.session.provider_service_label = None
            role_state.session.provider_package = None
            role_state.session.provider_included_summary = None
            role_state.session.provider_upgrade_summary = None
            role_state.session.provider_boundaries = None
            role_state.session.provider_climax_limit = None
            role_state.session.last_negotiation_summary = None
            role_state.session.provider_meeting_point = None
            role_state.session.provider_location_choice = None
            role_state.session.provider_location_pending = False
            role_state.session.provider_arrival_status = None
            role_state.session.provider_arrived_at_ts = None
            self._clear_communication_mode(role_state)
            
            # ========== RESET CLIMAX STATE ==========
            role_state.role_wants_climax = False
            role_state.role_holding_climax = False
            role_state.mas_wants_climax = False
            role_state.mas_holding_climax = False
            role_state.pending_ejakulasi_question = False
            # NOTE: mas_has_climaxed TIDAK direset karena itu history
            # NOTE: prefer_buang_di_dalam TIDAK direset karena diingat
            # NOTE: role_climax_count TIDAK direset karena history

            if role_id == ROLE_ID_NOVA:
                role_state.session_closure_summary = self._build_session_closure_summary(role_state)
                role_state.last_soft_end_ts = timestamp
                role_state.aftercare_active = False
                role_state.last_session_ended_at = timestamp
                continue

            if self._supports_soft_end(role_id):
                self._soft_end_role_session(role_state, timestamp)
                continue

            role_state.reset_intimacy_state()
            role_state.last_conversation_summary = None
            role_state.scene_memory.clear()
            role_state.sexual_moments.clear()
            self._reset_role_to_fresh_start(user_state.user_id, role_id)
            user_state.roles.pop(role_id, None)

        if previous_active_role_id in user_state.roles and not self._is_provider_role(previous_active_role_id):
            self.switch_active_role(user_state, previous_active_role_id)
        else:
            self.switch_active_role(user_state, ROLE_ID_NOVA)

    def _sync_global_session_mode(self, user_state: UserState) -> None:
        """Samakan mode global dengan sesi role aktif agar tidak bleed antar-role."""

        active_role_state = user_state.get_or_create_role_state(user_state.active_role_id)
        if active_role_state.session.active:
            user_state.global_session_mode = active_role_state.session.mode
        else:
            user_state.global_session_mode = SessionMode.NORMAL

    def switch_active_role(self, user_state: UserState, role_id: str) -> RoleState:
        """Pindah role aktif dengan sinkronisasi state global yang aman."""

        user_state.active_role_id = role_id
        role_state = user_state.get_or_create_role_state(role_id)
        apply_relationship_profile(role_state)
        self._sync_global_session_mode(user_state)
        return role_state

    def _reset_role_to_fresh_start(self, user_id: str, role_id: str) -> None:
        """Hapus semua memory eksternal untuk satu role agar mulai benar-benar baru."""

        if hasattr(self.message_history, "reset_role_history"):
            self.message_history.reset_role_history(user_id, role_id)
        if hasattr(self.story_memory, "reset_story"):
            self.story_memory.reset_story(user_id, role_id)
        if hasattr(self.milestones, "reset_role_milestones"):
            self.milestones.reset_role_milestones(user_id, role_id)

    def _is_provider_role(self, role_id: str) -> bool:
        from config.constants import is_provider_role
        return is_provider_role(role_id)

    def _get_extra_service_price(self, profile: ProviderProfile, extra_key: str) -> Optional[int]:
        """Ambil harga extra service berdasarkan key."""
        extra = profile.extra_services.get(extra_key)
        return extra.price if extra else None

    def _is_extra_service_available(self, profile: ProviderProfile, extra_key: str) -> bool:
        """Cek apakah extra service tersedia."""
        return extra_key in profile.extra_services

    # --------------------------------------------------
    # INTERNAL HELPERS: SIMPLE INTENT PARSING
    # --------------------------------------------------

    def _ensure_baseline_scene(self, role_state: RoleState) -> None:
      """Pastikan scene punya nilai dasar yang konsisten.

      Dipakai semua role kecuali ada override khusus.
      Tidak memaksa pindah lokasi/posture kalau sudah ada nilai.
      """
      scene = role_state.scene

      if not scene.location:
          scene.location = "ruang yang tenang"
      if not scene.posture:
          scene.posture = "duduk santai bersebelahan"
      if not scene.activity:
          scene.activity = "ngobrol berdua"
      if not scene.ambience:
          scene.ambience = "suasana hangat, lampu tidak terlalu terang"
      if scene.time_of_day is None:
          scene.time_of_day = TimeOfDay.NIGHT
      if not scene.physical_distance:
          scene.physical_distance = "sebelahan"

    def _infer_interaction_context(self, text: str) -> InteractionContext:
        """Heuristik sangat sederhana untuk menebak jenis interaksi."""

        t = text.lower()

        tone: str = "SOFT"
        content: str = "AFFECTION"
        strength = 1

        if any(word in t for word in ["kangen", "rindu", "miss you"]):
            tone = "SOFT"
            content = "AFFECTION"
            strength = 2
        if any(word in t for word in ["sayang", "love you", "cinta"]):
            tone = "SOFT"
            content = "AFFECTION"
            strength = max(strength, 2)
        if any(word in t for word in ["hehe", "wkwk", "haha", "nakal"]):
            tone = "PLAYFUL"
            content = "FLIRT"
        if any(word in t for word in ["capek", "lelah", "pusing", "down"]):
            tone = "DEEP"
            content = "SUPPORT"
        if any(word in t for word in ["marah", "kesel", "kesal", "nggak suka"]):
            tone = "CONFLICT"
            content = "REJECTION"
        if any(word in t for word in ["achhh", "enghh", "emmpph", "uchhh"]):
            tone = "SOFT"
            content = "HORNY"
            strength = max(strength, 2)

        return InteractionContext(
            tone=tone,  # type: ignore[arg-type]
            content=content,  # type: ignore[arg-type]
            strength=strength,
        )

    def _is_negative_text(self, text: str) -> bool:
        t = text.lower()
        negative_keywords = [
            "marah",
            "kesel",
            "kesal",
            "benci",
            "nggak suka",
            "ga suka",
            "gak suka",
            "diam",
            "cuek",
        ]
        return any(word in t for word in negative_keywords)

    # --------------------------------------------------
    # INTERNAL HELPERS: SCENE PER ROLE
    # --------------------------------------------------

    def _update_scene_for_role(self, role_state: RoleState, inp: OrchestratorInput) -> None:
        """Dispatch ke updater scene berdasarkan role_id."""

        self._ensure_baseline_scene(role_state)

        if role_state.role_id == ROLE_ID_NOVA:
            self._update_scene_for_nova(role_state, inp)
        elif role_state.role_id == ROLE_ID_TEMAN_KANTOR_IPEH:
            self._update_scene_for_ipeh(role_state, inp)
        elif role_state.role_id == ROLE_ID_TEMAN_LAMA_WIDYA:
            self._update_scene_for_widya(role_state, inp)
        elif role_state.role_id == ROLE_ID_IPAR_TASHA:
            self._update_scene_for_tasha(role_state, inp)
        elif role_state.role_id == ROLE_ID_BO_DAVINA:
            self._update_scene_for_sallsa(role_state, inp)
        elif role_state.role_id == ROLE_ID_BO_SALLSA:
            self._update_scene_for_sallsa(role_state, inp)
        elif role_state.role_id == ROLE_ID_TERAPIS_AGHIA:
            self._update_scene_for_aghia(role_state, inp)          
        else:
            role_state.scene.last_scene_update_ts = inp.timestamp

        if inp.remote_mode == "chat":
            self._apply_remote_chat_scene(role_state, inp.timestamp)
        elif inp.remote_mode == "call":
            self._apply_remote_call_scene(role_state, inp.timestamp)
        elif inp.remote_mode == "vps":
            self._apply_remote_vps_scene(role_state, inp.timestamp)

        self._normalize_role_room_label(role_state)

    def _normalize_role_room_label(self, role_state: RoleState) -> None:
        """Samakan label kamar privat agar semua role selain Nova memakai 'kamar kamu'."""

        if role_state.role_id == ROLE_ID_NOVA:
            return

        scene = role_state.scene
        location = (scene.location or "").lower()
        current_name = (getattr(role_state, "current_location_name", "") or "").lower()

        if any(marker in location for marker in ["kamar nova", "kamar utama"]) or any(
            marker in current_name for marker in ["kamar nova", "kamar utama"]
        ):
            return

        private_room_markers = [
            "kamar dietha",
            "kamar apartemen",
            "kamar",
        ]

        if any(marker in location for marker in private_room_markers):
            scene.location = "kamar kamu"
        if any(marker in current_name for marker in private_room_markers):
            role_state.current_location_name = "kamar kamu"

    def _apply_remote_chat_scene(self, role_state: RoleState, timestamp: float) -> None:
        """Override scene untuk percakapan yang terjadi lewat HP."""

        scene = role_state.scene
        scene.location = "masing-masing di tempat sendiri, terhubung lewat HP"
        scene.posture = "menatap layar HP sambil mengetik dan menunggu balasan"
        scene.activity = "komunikasi lewat chat WhatsApp atau Telegram"
        scene.ambience = "layar HP menyala, notifikasi masuk, suasana terasa personal dari kejauhan"
        scene.physical_distance = "berjauhan secara fisik, tapi tetap dekat lewat percakapan"
        scene.last_touch = "tidak ada sentuhan fisik karena interaksi terjadi lewat chat"
        scene.last_scene_update_ts = timestamp

    def _apply_remote_call_scene(self, role_state: RoleState, timestamp: float) -> None:
        """Override scene untuk percakapan lewat panggilan suara."""

        scene = role_state.scene
        scene.location = "masing-masing di tempat sendiri, terhubung lewat telepon"
        scene.posture = "memegang HP di telinga atau speaker sambil fokus mendengar suara satu sama lain"
        scene.activity = "komunikasi lewat panggilan suara"
        scene.ambience = "suara napas, jeda, dan intonasi terasa lebih dekat lewat sambungan telepon"
        scene.physical_distance = "berjauhan secara fisik, tapi terasa dekat lewat suara"
        scene.last_touch = "tidak ada sentuhan fisik karena interaksi terjadi lewat telepon"
        scene.last_scene_update_ts = timestamp

    def _apply_remote_vps_scene(self, role_state: RoleState, timestamp: float) -> None:
        """Override scene untuk percakapan lewat video call."""

        scene = role_state.scene
        scene.location = "masing-masing di tempat sendiri, saling terhubung lewat video call"
        scene.posture = "menatap layar HP sambil menjaga kamera tetap mengarah ke wajah atau tubuh"
        scene.activity = "komunikasi lewat video call privat"
        scene.ambience = "layar terang, kamera aktif, dan reaksi visual terasa langsung meski berjauhan"
        scene.physical_distance = "berjauhan secara fisik, tapi saling melihat secara real-time"
        scene.last_touch = "tidak ada sentuhan fisik karena interaksi terjadi lewat video call"
        scene.last_scene_update_ts = timestamp

    def _sync_household_scene_cues(self, role_state: RoleState, world_state: WorldState) -> None:
        """Sinkronkan cue rumah tangga yang perlu konsisten di scene."""

        scene = role_state.scene
        role_state.known_nova_status = world_state.nova_last_known_status
        if role_state.role_id == ROLE_ID_IPAR_TASHA:
            if world_state.nova_is_home or world_state.house_privacy_level == "guarded":
                if not scene.outfit:
                    scene.outfit = "baju rumah yang tipis tapi tetap rapi"
                if not scene.ambience:
                    scene.ambience = "suasana rumah yang tenang tapi tetap harus jaga sikap"
            else:
                if not scene.outfit:
                    scene.outfit = "tank top rumah tipis dan celana pendek santai"
                if world_state.house_privacy_level == "private":
                    scene.ambience = "rumah terasa lebih sepi, memberi ruang untuk tatapan dan obrolan yang lebih berani"

    def _get_default_outfit_for_context(self, role_state: RoleState) -> str:
        """Default outfit yang stabil sampai ada trigger ganti baju."""

        location = (getattr(role_state, "current_location_name", "") or role_state.scene.location or "").lower()
        role_id = role_state.role_id

        outside_markers = ["kafe", "mall", "restoran", "bioskop", "kantor", "parkiran", "mobil", "teras", "pantai", "taman"]
        apartment_markers = ["apartemen", "kamar apartemen"]
        if any(marker in location for marker in outside_markers):
            if role_id == ROLE_ID_NOVA:
                return "outfit luar yang Nova pilih sendiri"
            if role_id == ROLE_ID_IPAR_TASHA:
                return "outfit luar yang Dietha pilih sendiri"
            return "outfit luar yang dipilih role sendiri"
        if any(marker in location for marker in apartment_markers):
            return "outfit santai di apartemen yang tetap privat"
        home_defaults = [
            "tank top tipis dan short hotpants",
            "tank top rumah dan short hotpants",
            "daster pendek rumahan",
        ]
        return random.choice(home_defaults)

    def _build_initial_outfit_message(self, role_state: RoleState) -> str:
        """Bangun narasi outfit saat role pertama kali dipanggil."""

        outfit = role_state.scene.outfit or self._get_default_outfit_for_context(role_state)
        location = (getattr(role_state, "current_location_name", "") or role_state.scene.location or "").lower()
        role_label = role_state.role_display_name or role_state.role_id

        if any(marker in location for marker in ["kafe", "mall", "restoran", "bioskop", "kantor", "parkiran", "mobil", "teras", "pantai", "taman"]):
            return (
                f"*{role_label} muncul dengan outfit luar pilihannya sendiri* "
                f'"Aku tadi pilih yang ini ya, Mas... aku pakai {outfit}."'
            )

        home_options = [
            f'*{role_label} terlihat santai di rumah* "Mas... aku lagi pakai {outfit}."',
            f'*{role_label} membenarkan bajunya pelan* "Di rumah aku pakai {outfit} ya, Mas."',
            f'*{role_label} menoleh sambil merapikan outfit rumahnya* "Sekarang aku pakai {outfit}."',
        ]
        return random.choice(home_options)

    def _update_outfit_continuity(self, role_state: RoleState, user_text: str) -> None:
        """Pertahankan outfit sampai ada trigger ganti baju yang jelas."""

        text = user_text.lower()
        scene = role_state.scene

        if not scene.outfit:
            scene.outfit = self._get_default_outfit_for_context(role_state)

        if any(kw in text for kw in ["ganti baju", "ganti outfit", "pakai yang lain", "daster", "tank top", "dress", "rok", "jeans", "kaos"]):
            if any(kw in text for kw in ["daster", "daster pendek"]):
                scene.outfit = "daster pendek rumahan"
            elif "tank top" in text:
                scene.outfit = "tank top tipis dan short hotpants"
            elif any(kw in text for kw in ["dress", "rok", "jeans", "blouse", "jaket", "kaos"]):
                scene.outfit = "outfit baru yang dipilih untuk keluar"
            role_state.outfit_changed_this_session = True
                  
    # ========== TAMBAHKAN METHOD INI DI SINI ==========
    def _detect_lap_proximity(self, role_state: RoleState, text: str) -> bool:
        """Deteksi apakah user meminta role duduk di pangkuan."""
        from core.state_models import IntimacyPhase, SceneSequence, SexPosition, IntimacyIntensity
        
        t = text.lower()
        
        lap_keywords = [
            "duduk dipangku", "duduk di pangkuan", "naik ke pangkuan",
            "duduk di pangku", "pangku", "duduk di atas pangkuan",
            "duduk di pangku aku", "naik ke pangku aku"
        ]
        
        if any(kw in t for kw in lap_keywords):
            # Update scene untuk semua role
            role_state.scene.posture = "duduk di pangkuan Mas"
            role_state.scene.physical_distance = "sangat dekat, tubuh menempel"
            role_state.scene.activity = "bersandar di dada Mas sambil ngobrol"
            role_state.scene.last_touch = "pelukan dari depan"
            
            # Update intimacy detail
            role_state.intimacy_detail.position = SexPosition.SITTING
            if role_state.intimacy_detail.intensity == IntimacyIntensity.FOREPLAY:
                role_state.intimacy_detail.intensity = IntimacyIntensity.PETTING
            
            # Catat bahwa sudah pernah duduk dipangku
            role_state.lap_proximity_established = True
            
            # Jika intimacy sudah cukup, naikkan fase
            # LANGSUNG, tanpa cek
            if role_state.intimacy_phase == IntimacyPhase.DEKAT:
                role_state.intimacy_phase = IntimacyPhase.INTIM
                role_state.current_sequence = SceneSequence.PELUKAN
                logger.info(f"🔥 {role_state.role_id} fase naik ke INTIM karena duduk dipangku")
            
            # Naikkan unlock score
            if role_state.high_intensity_unlock_score < 70:
                role_state.high_intensity_unlock_score = min(100, role_state.high_intensity_unlock_score + 15)
                logger.info(f"📈 {role_state.role_id} unlock_score +15 karena duduk dipangku")
            
            return True
        
        return False
    # ========== AKHIR TAMBAHAN ==========

    # --------------------------------------------------
    # INTERNAL HELPERS: SCENE UNTUK NOVA
    # --------------------------------------------------

    def _update_scene_for_nova(self, role_state: RoleState, inp: OrchestratorInput) -> None:
        """Update SceneState Nova dengan eskalasi bertahap."""

        scene = role_state.scene
        t = inp.text.lower()
        phase = role_state.intimacy_phase

        # Baseline sekali saja
        if not scene.location:
            scene.location = "kamar Nova"
        if not scene.posture:
            scene.posture = "duduk santai"
        if not scene.activity:
            scene.activity = "ngobrol berdua"
        if not scene.ambience:
            scene.ambience = "suasana tenang, lampu tidak terlalu terang"
        if scene.time_of_day is None:
            scene.time_of_day = TimeOfDay.NIGHT
        if not scene.physical_distance:
            scene.physical_distance = "sebelahan"
        if not scene.outfit:
            scene.outfit = "tank top tipis dan short hotpants"

        # ========== KAMAR / KASUR - ESKALASI BERTAHAP ==========
        if any(kw in t for kw in ["kamar nova", "kamar kakak", "kamar utama", "kasur", "ranjang"]):
            scene.location = "kamar Nova"
            if phase == IntimacyPhase.VULGAR:
                scene.posture = "berbaring bersebelahan"
                scene.activity = "bercengkrama sambil berbaring"
                scene.ambience = "lampu redup, suasana hangat dan intim"
            elif phase == IntimacyPhase.INTIM:
                if any(kw in t for kw in ["duduk dipangku", "naik ke pangkuan", "minta dipangku", "pangku", "deket"]):
                    scene.posture = "duduk di pangkuan Mas"
                    scene.activity = "bersandar di dada Mas sambil ngobrol"
                    scene.ambience = "suasana hangat, napas mulai beradu"
                    if not hasattr(role_state, 'lap_proximity_established'):
                        role_state.lap_proximity_established = True
                else:
                    scene.posture = "duduk bersebelahan"
                    scene.activity = "ngobrol santai"
                    scene.ambience = "suasana kamar yang hangat"
            else:
                scene.posture = "duduk bersebelahan"
                scene.activity = "ngobrol santai"
                scene.ambience = "suasana kamar yang nyaman"
        elif any(kw in t for kw in ["kamar", "kamar tidur"]):
            scene.location = "kamar Nova"
            if phase == IntimacyPhase.VULGAR:
                scene.posture = "berbaring bersebelahan"
                scene.activity = "bercengkrama sambil berbaring"
                scene.ambience = "lampu redup, suasana hangat dan intim"
            elif phase == IntimacyPhase.INTIM:
                # Deteksi apakah minta dipangku atau mendekat
                if any(kw in t for kw in ["duduk dipangku", "naik ke pangkuan", "minta dipangku", "pangku", "deket"]):
                    scene.posture = "duduk di pangkuan Mas"
                    scene.activity = "bersandar di dada Mas sambil ngobrol"
                    scene.ambience = "suasana hangat, napas mulai beradu"
                    if not hasattr(role_state, 'lap_proximity_established'):
                        role_state.lap_proximity_established = True
                else:
                    scene.posture = "duduk bersebelahan"
                    scene.activity = "ngobrol santai"
                    scene.ambience = "suasana kamar yang hangat"
            else:
                scene.posture = "duduk bersebelahan"
                scene.activity = "ngobrol santai"
                scene.ambience = "suasana kamar yang nyaman"

        # Sentuhan / pelukan / sender (tetap sopan di INTIM)
        if any(word in t for word in ["peluk", "pelukan"]):
            if phase == IntimacyPhase.VULGAR:
                self.scene_engine.gentle_hug(scene)
            else:
                scene.last_touch = "pelukan ringan"
                scene.physical_distance = "dekat"

        if any(word in t for word in ["sender", "nyender"]):
            scene.last_touch = "menyender di bahu"
            scene.physical_distance = "dekat"

        # Jarak fisik eksplisit dari teks
        if any(kw in t for kw in ["mepet", "deket", "dekat", "rapat"]):
            scene.physical_distance = "sangat dekat"

        # Outfit sederhana
        if "piyama" in t or "pyjama" in t:
            scene.outfit = "piyama santai yang nyaman"
        elif "dress" in t:
            scene.outfit = "dress sederhana yang lembut"
        elif "kaos" in t or "t-shirt" in t:
            scene.outfit = "kaos santai dan celana pendek"

        scene.last_scene_update_ts = inp.timestamp
      
    # --------------------------------------------------
    # INTERNAL HELPERS: SCENE UNTUK TASHA
    # --------------------------------------------------

    def _update_scene_for_tasha(self, role_state: RoleState, inp: OrchestratorInput) -> None:
        """Update SceneState untuk Tasha Dietha (ipar_tasha)."""

        scene = role_state.scene
        t = inp.text.lower()
        phase = role_state.intimacy_phase

        # Default baseline: ruang keluarga di rumah keluarga
        if not scene.location:
            scene.location = "ruang keluarga di rumah keluarga"
        if not scene.posture:
            scene.posture = "duduk di sofa, Dietha agak miring ke arah Mas"
        if not scene.activity:
            scene.activity = "ngobrol santai sambil nonton TV yang pelan"
        if not scene.ambience:
            scene.ambience = "suasana rumah tenang, lampu hangat, kadang suara TV pelan"
        if scene.time_of_day is None:
            scene.time_of_day = TimeOfDay.EVENING
        if not scene.physical_distance:
            scene.physical_distance = "cukup dekat, bahu hampir bersentuhan"
        if not scene.outfit:
            scene.outfit = "tank top tipis dan short hotpants"

        # User menyebut dapur / masak bareng
        if any(kw in t for kw in ["dapur", "masak", "kitchen"]):
            scene.location = "dapur rumah keluarga"
            scene.posture = "berdiri cukup dekat di depan meja dapur"
            scene.activity = "sibuk masak/bareng, sesekali saling melirik"
            scene.ambience = "suasana rumah hangat, aroma masakan, kadang suara panci"

        # User menyebut teras / halaman / depan rumah
        if any(kw in t for kw in ["teras", "depan rumah", "halaman"]):
            scene.location = "teras depan rumah keluarga"
            scene.posture = "duduk bersebelahan di bangku teras"
            scene.activity = "ngobrol pelan sambil lihat jalan depan rumah"
            scene.ambience = "suasana malam agak sepi, lampu teras kuning hangat"

        # ========== KAMAR - SESUAIKAN DENGAN FASE ==========
        if "kamar dietha" in t or "kamar tasha" in t or "kamar ipar" in t:
            scene.location = "kamar Dietha"
            if phase == IntimacyPhase.VULGAR:
                scene.posture = "duduk berhadapan di kasur, tubuh berdekatan"
                scene.activity = "menikmati kebersamaan yang lebih intens"
                scene.ambience = "lampu redup, suasana hangat dan intim"
            elif phase == IntimacyPhase.INTIM:
                scene.posture = "duduk bersebelahan di tepi kasur"
                scene.activity = "ngobrol santai sambil sesekali melirik"
                scene.ambience = "suasana kamar yang tenang, lampu tidur menyala pelan"
            else:
                scene.posture = "duduk di tepi kasur dengan jarak sopan"
                scene.activity = "mengobrol biasa"
                scene.ambience = "suasana kamar Dietha yang nyaman"
        elif "kamar nova" in t or "kamar kakak" in t or "kamar utama" in t:
            scene.location = "kamar Nova"
            scene.posture = "berdiri atau duduk dengan hati-hati di dekat pintu"
            scene.activity = "masuk sebentar sambil tetap sadar itu kamar Kakak dan Mas"
            scene.ambience = "suasana kamar utama yang privat milik Nova dan Mas"
        elif "kamar tamu" in t:
            scene.location = "kamar tamu"
            scene.posture = "duduk bersebelahan di tepi kasur tamu"
            scene.activity = "ngobrol pelan di ruang yang lebih sepi"
            scene.ambience = "suasana kamar tamu yang rapi dan tenang"
        elif "kamar" in t or "room" in t:
            scene.location = "kamar Dietha"
            if phase == IntimacyPhase.VULGAR:
                scene.posture = "duduk berhadapan di kasur, tubuh berdekatan"
                scene.activity = "menikmati kebersamaan yang lebih intens"
                scene.ambience = "lampu redup, suasana hangat dan intim"
            elif phase == IntimacyPhase.INTIM:
                scene.posture = "duduk bersebelahan di tepi kasur"
                scene.activity = "ngobrol santai sambil sesekali melirik"
                scene.ambience = "suasana kamar yang tenang, lampu tidur menyala pelan"
            else:
                scene.posture = "duduk di tepi kasur dengan jarak sopan"
                scene.activity = "mengobrol biasa"
                scene.ambience = "suasana kamar yang nyaman"

        # ========== KASUR / TEMPAT TIDUR - ESKALASI BERTAHAP ==========
        if any(kw in t for kw in ["kasur", "ranjang"]):
            scene.location = scene.location or "kamar Dietha"
            if phase == IntimacyPhase.VULGAR:
                scene.posture = "duduk di pangkuan Mas"
                scene.activity = "berpelukan erat"
                scene.ambience = "lampu redup, suasana sangat intim"
            elif phase == IntimacyPhase.INTIM:
                # Deteksi apakah user minta dipangku atau role inisiatif
                if any(kw in t for kw in ["duduk dipangku", "naik ke pangkuan", "minta dipangku", "pangku"]):
                    scene.posture = "duduk di pangkuan Mas"
                    scene.activity = "bersandar di dada Mas sambil ngobrol"
                    scene.ambience = "suasana kamar hangat, napas mulai beradu"
                    # Catat bahwa sudah ada inisiatif mendekat
                    if not hasattr(role_state, 'lap_proximity_established'):
                        role_state.lap_proximity_established = True
                else:
                    scene.posture = "duduk bersebelahan di kasur"
                    scene.activity = "ngobrol sambil sesekali bersandar"
                    scene.ambience = "suasana kamar yang hangat"
            else:
                scene.posture = "duduk di tepi kasur dengan jarak sopan"
                scene.activity = "mengobrol biasa"
                scene.ambience = "suasana kamar yang nyaman"

        # ========== DUDUK DI PANGKUAN / MEMELUK - ESKALASI ==========
        if any(kw in t for kw in ["duduk dipangku", "naik ke pangkuan", "duduk di pangkuan", "memeluk dari belakang"]):
            if phase == IntimacyPhase.INTIM:
                # Di INTIM, ini masih wajar sebagai bentuk kedekatan
                scene.posture = "duduk di pangkuan Mas"
                scene.activity = "bersandar di dada Mas sambil ngobrol"
                scene.ambience = "suasana hangat, napas mulai beradu"
                if not hasattr(role_state, 'lap_proximity_established'):
                    role_state.lap_proximity_established = True
            elif phase == IntimacyPhase.VULGAR:
                scene.posture = "duduk di pangkuan Mas, tubuh saling menempel"
                scene.activity = "menikmati kedekatan yang semakin dalam"
                scene.ambience = "lampu redup, suasana sangat intim"

        # ========== PETTING / SENTUHAN LANJUTAN - HANYA JIKA SUDAH ADA ESKALASI ==========
        if any(kw in t for kw in ["petting", "gesek", "gesek memek ke batang kontol"]):
            # Cek apakah sudah ada eskalasi (duduk dipangkuan) atau sudah VULGAR
            has_escalation = getattr(role_state, 'lap_proximity_established', False) or phase == IntimacyPhase.VULGAR
            
            if phase == IntimacyPhase.VULGAR:
                scene.posture = "duduk dipangkuan Mas"
                scene.activity = "menikmati kedekatan yang semakin dalam"
                scene.ambience = "lampu redup, suasana sangat intim"
            elif has_escalation and phase == IntimacyPhase.INTIM:
                # Masih di INTIM tapi sudah ada eskalasi, user mungkin mencoba memberikan rangsangan
                # Belum pindah ke VULGAR, tapi catat sebagai pending
                scene.posture = "duduk di pangkuan Mas"
                scene.activity = "bernafas lebih berat, tubuh mulai merespon"
                scene.ambience = "suasana makin hangat, napas beradu"
                # Catat bahwa user sedang memberikan rangsangan
                role_state.pending_arousal_signals = getattr(role_state, 'pending_arousal_signals', 0) + 1
            else:
                # Belum ada eskalasi, abaikan atau turunkan ke sentuhan ringan
                scene.posture = "duduk berdekatan"
                scene.activity = "berpegangan tangan"
                scene.ambience = "suasana hangat"

        # User menyebut mobil / parkiran → momen berdua di luar rumah
        if "mobil" in t or "parkiran" in t or "parkir" in t:
            scene.location = "mobil Mas di parkiran dekat rumah"
            scene.posture = "duduk di kursi depan, Dietha di samping Mas"
            scene.activity = "ngobrol pelan sebelum pulang, kadang saling terdiam canggung"
            scene.ambience = "suasana malam, lampu jalan dari luar kaca"

        # Jarak fisik & sentuhan halus ala ipar
        if any(kw in t for kw in ["mepet", "deket", "dekat", "rapat"]):
            scene.physical_distance = "sangat dekat, paha bersentuhan"

        if any(kw in t for kw in ["pegang tangan", "genggam tangan", "pegangan tangan"]):
            scene.last_touch = "genggam tangan singkat dan lama"

        if any(kw in t for kw in ["sender", "nyender", "sandaran"]):
            scene.last_touch = "Dietha menyender pelan ke dada Mas, minta peluk"

        scene.last_scene_update_ts = inp.timestamp
      
    # --------------------------------------------------
    # INTERNAL HELPERS: SCENE UNTUK IPEH (TEMAN KANTOR)
    # --------------------------------------------------

    def _update_scene_for_ipeh(self, role_state: RoleState, inp: OrchestratorInput) -> None:
        """Update SceneState untuk Ipeh (teman_kantor_ipeh) dengan eskalasi bertahap."""

        scene = role_state.scene
        t = inp.text.lower()
        phase = role_state.intimacy_phase

        # Default baseline di kantor
        if not scene.location:
            scene.location = "ruang kerja kantor"
        if not scene.posture:
            scene.posture = "duduk di kursi kantor bersebelahan"
        if not scene.activity:
            scene.activity = "ngobrol sambil ngerjain tugas ringan"
        if not scene.ambience:
            scene.ambience = "suasana kantor agak ramai tapi hangat"
        if scene.time_of_day is None:
            scene.time_of_day = TimeOfDay.EVENING

        # User merasa sumpek / jenuh di kantor
        if any(kw in t for kw in ["sumpek", "jenuh", "bosen", "bosan"]):
            scene.ambience = "ruang kantor terasa sumpek dan melelahkan"

        # Mention kafe / kerja di luar kantor
        if "kafe" in t or "cafe" in t or "cafÃ©" in t:
            scene.location = "kafe dekat kantor"
            scene.posture = "duduk bersebelahan di sofa kafe"
            scene.activity = "ngerjain presentasi bareng sambil ngopi"
            scene.ambience = "lampu temaram, suasana cozy dengan musik pelan"

        # Mention mobil
        if "mobil" in t:
            scene.location = "mobil Mas di parkiran kantor"
            scene.posture = "duduk di kursi depan, Ipeh di samping Mas"
            scene.activity = "ngobrol santai sambil siap berangkat"
            scene.ambience = "suasana malam, lampu jalan dari luar kaca"

        # ========== KAMAR - ESKALASI BERTAHAP ==========
        if "kamar" in t or "room" in t:
            scene.location = "kamar apartemen"
            if phase == IntimacyPhase.VULGAR:
                scene.posture = "duduk berhadapan di kasur"
                scene.activity = "menikmati kebersamaan"
                scene.ambience = "lampu redup, suasana intim"
            elif phase == IntimacyPhase.INTIM:
                if any(kw in t for kw in ["duduk dipangku", "naik ke pangkuan", "minta dipangku", "pangku"]):
                    scene.posture = "duduk di pangkuan Mas"
                    scene.activity = "bersandar di dada Mas sambil ngobrol"
                    scene.ambience = "suasana hangat, napas mulai beradu"
                    if not hasattr(role_state, 'lap_proximity_established'):
                        role_state.lap_proximity_established = True
                else:
                    scene.posture = "duduk bersebelahan di kasur"
                    scene.activity = "ngobrol santai"
                    scene.ambience = "suasana kamar yang nyaman"
            else:
                scene.posture = "duduk bersebelahan di kasur"
                scene.activity = "ngobrol santai"
                scene.ambience = "suasana kamar yang nyaman"

        # ========== TEMPAT TUGAS / LEMBUR - HANYA VULGAR YANG INTIM ==========
        if any(kw in t for kw in ["tugas", "lembur", "pulang malam"]):
            if phase == IntimacyPhase.VULGAR:
                scene.location = "ruang kantor yang sepi"
                scene.posture = "duduk berdekatan di sofa kantor"
                scene.activity = "melepas penat setelah lembur"
                scene.ambience = "lampu kantor redup, suasana hening"
            else:
                scene.location = "ruang kantor"
                scene.posture = "duduk di kursi masing-masing"
                scene.activity = "menyelesaikan tugas"
                scene.ambience = "suasana kantor malam yang sepi"

        # Jarak fisik & sentuhan halus
        if any(kw in t for kw in ["mepet", "deket", "dekat", "rapat"]):
            scene.physical_distance = "sangat dekat, paha bersentuhan"

        if any(kw in t for kw in ["pegang tangan", "genggam tangan", "pegangan tangan"]):
            scene.last_touch = "genggam tangan singkat dan lama"

        if any(kw in t for kw in ["sender", "nyender", "sandaran"]):
            scene.last_touch = "Ipeh menyender pelan ke bahu Mas"

        scene.last_scene_update_ts = inp.timestamp
    
    # --------------------------------------------------
    # INTERNAL HELPERS: SCENE UNTUK WIDYA (TEMAN LAMA)
    # --------------------------------------------------

    def _update_scene_for_widya(self, role_state: RoleState, inp: OrchestratorInput) -> None:
        """Update SceneState untuk Widya (teman_lama_widya) dengan eskalasi bertahap."""

        scene = role_state.scene
        t = inp.text.lower()
        phase = role_state.intimacy_phase

        # Default baseline: kafe tenang / tempat nongkrong nostalgia
        if not scene.location:
            scene.location = "kafe tenang yang sering kalian datangi dulu"
        if not scene.posture:
            scene.posture = "duduk bersebelahan di sofa kafe"
        if not scene.activity:
            scene.activity = "ngobrol santai sambil minum kopi dan tertawa kecil"
        if not scene.ambience:
            scene.ambience = "lampu temaram, suasana cozy dengan musik pelan"
        if scene.time_of_day is None:
            scene.time_of_day = TimeOfDay.EVENING
        if not scene.physical_distance:
            scene.physical_distance = "cukup dekat, bahu hampir bersentuhan"

        # User merasa sumpek / butuh udara segar → pindah ke luar
        if any(kw in t for kw in ["sumpek", "jenuh", "bosen", "bosan"]):
            scene.location = "teras kafe yang menghadap jalan"
            scene.posture = "duduk bersebelahan menghadap luar"
            scene.activity = "ngobrol sambil lihat lampu jalan"
            scene.ambience = "udara malam yang agak sejuk, lampu jalan berkelip"

        # Mention kafe / coffee shop eksplisit
        if "kafe" in t or "cafe" in t or "cafÃ©" in t or "coffee shop" in t:
            scene.location = "kafe tenang dengan sofa empuk"
            scene.posture = "duduk bersebelahan di sofa"
            scene.activity = "ngobrol nostalgia sambil minum kopi"
            scene.ambience = "lampu temaram, musik pelan"

        # Mention mobil → nostalgia di mobil / pulang bareng
        if "mobil" in t or "parkiran" in t:
            scene.location = "mobil Mas di parkiran kafe"
            scene.posture = "duduk di kursi depan, Widya di samping Mas"
            scene.activity = "ngobrol santai sebelum pulang"
            scene.ambience = "suasana malam, lampu jalan terlihat dari kaca depan"

        # Mention balkon / rooftop / pantai → spot nostalgia romantis
        if any(kw in t for kw in ["balkon", "rooftop", "atap"]):
            scene.location = "rooftop gedung dengan city lights di kejauhan"
            scene.posture = "berdiri bersebelahan di pagar"
            scene.activity = "ngobrol pelan sambil lihat lampu kota"
            scene.ambience = "angin malam sejuk, suasana agak sepi"

        if "pantai" in t or "losari" in t:
            scene.location = "pinggir pantai yang tenang di malam hari"
            scene.posture = "duduk bersebelahan di bangku menghadap laut"
            scene.activity = "ngobrol nostalgia sambil dengar suara ombak"
            scene.ambience = "suasana malam, angin laut"

        # ========== KAMAR / TEMPAT PRIVAT - ESKALASI BERTAHAP ==========
        if "kamar" in t or "room" in t:
            scene.location = "kamar"
            if phase == IntimacyPhase.VULGAR:
                scene.posture = "duduk berhadapan di kasur"
                scene.activity = "menikmati kebersamaan"
                scene.ambience = "lampu redup, suasana intim"
            elif phase == IntimacyPhase.INTIM:
                if any(kw in t for kw in ["duduk dipangku", "naik ke pangkuan", "minta dipangku", "pangku"]):
                    scene.posture = "duduk di pangkuan Mas"
                    scene.activity = "bersandar di dada Mas"
                    scene.ambience = "suasana hangat, napas mulai beradu"
                    if not hasattr(role_state, 'lap_proximity_established'):
                        role_state.lap_proximity_established = True
                else:
                    scene.posture = "duduk bersebelahan di kasur"
                    scene.activity = "ngobrol santai"
                    scene.ambience = "suasana kamar yang hangat"

        # Jarak fisik & sentuhan halus
        if any(kw in t for kw in ["mepet", "deket", "dekat", "rapat"]):
            scene.physical_distance = "sangat dekat, paha hampir bersentuhan"

        if any(kw in t for kw in ["pegang tangan", "genggam tangan", "pegangan tangan"]):
            scene.last_touch = "genggam tangan singkat tapi hangat"

        if any(kw in t for kw in ["sandaran", "nyender", "sender"]):
            scene.last_touch = "Widya menyender pelan ke bahu Mas"

        scene.last_scene_update_ts = inp.timestamp

    # --------------------------------------------------
    # INTERNAL HELPERS: SCENE UNTUK SISKA (WANITA BERSUAMI)
    # --------------------------------------------------

    def _update_scene_for_siska(self, role_state: RoleState, inp: OrchestratorInput) -> None:
        """Update SceneState untuk Siska (wanita bersuami) dengan eskalasi bertahap."""

        scene = role_state.scene
        t = inp.text.lower()
        phase = role_state.intimacy_phase

        # Default baseline: ruang tamu/keluarga yang relatif aman
        if not scene.location:
            scene.location = "ruang tamu rumah Siska"
        if not scene.posture:
            scene.posture = "duduk di sofa, Siska agak miring ke arah Mas tapi masih jaga jarak"
        if not scene.activity:
            scene.activity = "ngobrol pelan sambil sesekali melirik jam atau pintu"
        if not scene.ambience:
            scene.ambience = "suasana rumah tenang, lampu hangat, kadang terdengar suara dari ruangan lain"
        if scene.time_of_day is None:
            scene.time_of_day = TimeOfDay.EVENING
        if not scene.physical_distance:
            scene.physical_distance = "cukup dekat tapi masih berjarak sopan"

        # Dapur / masak bareng
        if any(kw in t for kw in ["dapur", "masak", "kitchen"]):
            scene.location = "dapur rumah Siska"
            scene.posture = "berdiri cukup dekat di depan meja dapur"
            scene.activity = "menyiapkan minuman atau makanan sambil ngobrol pelan"
            scene.ambience = "suasana rumah hangat, aroma masakan"

        # Teras / depan rumah
        if any(kw in t for kw in ["teras", "depan rumah", "halaman"]):
            scene.location = "teras depan rumah Siska"
            scene.posture = "duduk bersebelahan di bangku teras"
            scene.activity = "ngobrol pelan sambil melihat jalan depan rumah"
            scene.ambience = "suasana malam agak sepi, lampu teras temaram"

        # ========== KAMAR TAMU - ESKALASI BERTAHAP ==========
        if "kamar" in t or "room" in t:
            scene.location = "kamar tamu di rumah Siska"
            if phase == IntimacyPhase.VULGAR:
                scene.posture = "duduk berhadapan di tepi kasur"
                scene.activity = "bercengkrama dengan suasana yang lebih akrab"
                scene.ambience = "lampu redup, suasana hening"
            elif phase == IntimacyPhase.INTIM:
                if any(kw in t for kw in ["duduk dipangku", "naik ke pangkuan", "minta dipangku", "pangku"]):
                    scene.posture = "duduk di pangkuan Mas"
                    scene.activity = "bersandar di dada Mas, Siska tampak ragu"
                    scene.ambience = "suasana hening, jantung berdebar"
                    if not hasattr(role_state, 'lap_proximity_established'):
                        role_state.lap_proximity_established = True
                else:
                    scene.posture = "duduk di tepi kasur dengan jarak sopan"
                    scene.activity = "ngobrol pelan tentang hal pribadi"
                    scene.ambience = "suasana hening, lampu redup"

        # Mobil / parkiran → momen berdua di luar rumah
        if "mobil" in t or "parkir" in t or "parkiran" in t:
            scene.location = "mobil Mas di parkiran dekat rumah Siska"
            scene.posture = "duduk di kursi depan, Siska di samping Mas"
            scene.activity = "ngobrol pelan sebelum pulang"
            scene.ambience = "suasana malam, lampu jalan dari luar kaca"

        # Jarak fisik & sentuhan
        if any(kw in t for kw in ["mepet", "deket", "dekat", "rapat"]):
            scene.physical_distance = "sangat dekat, Siska tampak gelisah"

        if any(kw in t for kw in ["pegang tangan", "genggam tangan", "pegangan tangan"]):
            scene.last_touch = "genggam tangan singkat yang membuat Siska tampak bimbang"

        if any(kw in t for kw in ["sender", "nyender", "sandaran"]):
            scene.last_touch = "Siska menyender pelan ke bahu Mas"

        scene.last_scene_update_ts = inp.timestamp

    # --------------------------------------------------
    # INTERNAL HELPERS: SCENE UNTUK SALLSA (TEMAN SPESIAL)
    # --------------------------------------------------

    def _update_scene_for_sallsa(self, role_state: RoleState, inp: OrchestratorInput) -> None:
        """Update SceneState untuk Sallsa (teman_spesial_sallsa)."""

        scene = role_state.scene
        t = inp.text.lower()
        phase = role_state.intimacy_phase

        # Default baseline: sofa/apartemen malam hari (suasana manja & playful)
        if not scene.location:
            scene.location = "ruang keluarga apartemen Mas dengan sofa empuk"
        if not scene.posture:
            scene.posture = "duduk bersebelahan di sofa, Sallsa agak mepet ke Mas"
        if not scene.activity:
            scene.activity = "ngobrol santai sambil nonton TV pelan atau scroll HP bareng"
        if not scene.ambience:
            scene.ambience = "lampu hangat agak redup, suasana malam santai dan hangat"
        if scene.time_of_day is None:
            scene.time_of_day = TimeOfDay.NIGHT
        if not scene.physical_distance:
            scene.physical_distance = "sangat dekat, bahu saling bersentuhan"

        # ========== SOFA - ESKALASI BERTAHAP ==========
        if any(kw in t for kw in ["sofa", "ruang tamu"]):
            scene.location = "sofa ruang tamu"
            if phase == IntimacyPhase.VULGAR:
                scene.posture = "duduk berhadapan di sofa, tubuh berdekatan"
                scene.activity = "menikmati kebersamaan yang semakin dalam"
                scene.ambience = "lampu redup, suasana hangat dan intim"
            elif phase == IntimacyPhase.INTIM:
                # Deteksi apakah user minta dipangku atau role inisiatif
                if any(kw in t for kw in ["duduk dipangku", "naik ke pangkuan", "minta dipangku", "pangku"]):
                    scene.posture = "duduk di pangkuan Mas"
                    scene.activity = "bersandar di dada Mas sambil ngobrol"
                    scene.ambience = "suasana hangat, napas mulai beradu"
                    if not hasattr(role_state, 'lap_proximity_established'):
                        role_state.lap_proximity_established = True
                else:
                    scene.posture = "duduk bersebelahan di sofa"
                    scene.activity = "nonton TV sambil bersandar"
                    scene.ambience = "suasana santai, lampu hangat"
            else:
                scene.posture = "duduk bersebelahan di sofa"
                scene.activity = "ngobrol santai"
                scene.ambience = "suasana santai"

        # ========== KAMAR / KASUR - SESUAIKAN DENGAN FASE ==========
        if "kamar" in t or "bed" in t or "kasur" in t:
            scene.location = "kamar apartemen"
            if phase == IntimacyPhase.VULGAR:
                scene.posture = "duduk berhadapan di kasur"
                scene.activity = "menikmati kebersamaan"
                scene.ambience = "lampu redup, suasana hangat dan intim"
            elif phase == IntimacyPhase.INTIM:
                if any(kw in t for kw in ["duduk dipangku", "naik ke pangkuan", "minta dipangku", "pangku"]):
                    scene.posture = "duduk di pangkuan Mas"
                    scene.activity = "bersandar di dada Mas"
                    scene.ambience = "suasana kamar yang hangat"
                    if not hasattr(role_state, 'lap_proximity_established'):
                        role_state.lap_proximity_established = True
                else:
                    scene.posture = "duduk bersebelahan di kasur"
                    scene.activity = "ngobrol santai sambil rebahan"
                    scene.ambience = "suasana kamar yang nyaman"
            else:
                scene.posture = "duduk bersebelahan di kasur"
                scene.activity = "ngobrol santai"
                scene.ambience = "suasana kamar yang nyaman"

        # ========== DUDUK DI PANGKUAN / MEMELUK ==========
        if any(kw in t for kw in ["duduk dipangku", "naik ke pangkuan", "duduk di pangkuan", "memeluk"]):
            if phase == IntimacyPhase.INTIM:
                scene.posture = "duduk di pangkuan Mas"
                scene.activity = "bersandar di dada Mas sambil ngobrol"
                scene.ambience = "suasana hangat, napas mulai beradu"
                if not hasattr(role_state, 'lap_proximity_established'):
                    role_state.lap_proximity_established = True
            elif phase == IntimacyPhase.VULGAR:
                scene.posture = "duduk di pangkuan Mas, tubuh saling menempel"
                scene.activity = "menikmati kedekatan yang semakin dalam"
                scene.ambience = "lampu redup, suasana sangat intim"

        # ========== SENTUHAN LANJUTAN - HANYA JIKA SUDAH ADA ESKALASI ==========
        if any(kw in t for kw in ["pegang", "remas", "usap", "elus", "raba"]):
            has_escalation = getattr(role_state, 'lap_proximity_established', False) or phase == IntimacyPhase.VULGAR
            
            if phase == IntimacyPhase.VULGAR:
                scene.activity = "menikmati sentuhan yang semakin dalam"
            elif has_escalation and phase == IntimacyPhase.INTIM:
                scene.activity = "bernafas lebih berat, tubuh mulai merespon"
                role_state.pending_arousal_signals = getattr(role_state, 'pending_arousal_signals', 0) + 1
            else:
                scene.activity = "berpegangan tangan"

        # Balkon / rooftop / view city lights
        if any(kw in t for kw in ["balkon", "balcony", "rooftop", "atap"]):
            scene.location = "balkon apartemen dengan city lights di kejauhan"
            scene.posture = "berdiri bersebelahan di pagar balkon"
            scene.activity = "menikmati pemandangan kota sambil ngobrol"
            scene.ambience = "angin malam sejuk, lampu kota berkelip"

        # Mobil / jalan malam
        if "mobil" in t or "parkir" in t or "parkiran" in t:
            scene.location = "mobil Mas di parkiran mall atau apartemen"
            scene.posture = "duduk di kursi depan, Sallsa di samping Mas"
            scene.activity = "ngobrol santai sambil duduk di mobil"
            scene.ambience = "suasana malam, lampu jalan dari luar kaca"

        # Coffee shop / tempat santai lain
        if any(kw in t for kw in ["kafe", "cafe", "café", "coffee shop"]):
            scene.location = "kafe santai dengan sofa empuk"
            scene.posture = "duduk bersebelahan di sofa kafe"
            scene.activity = "ngobrol rame sambil minum minuman manis favorit"
            scene.ambience = "musik pelan, lampu temaram, suasana cozy"

        # Jarak fisik & sentuhan
        if any(kw in t for kw in ["mepet", "deket", "dekat", "rapat"]):
            scene.physical_distance = "sangat dekat"

        if any(kw in t for kw in ["peluk", "pelukan"]):
            if phase == IntimacyPhase.VULGAR:
                scene.last_touch = "berpelukan erat"
            else:
                scene.last_touch = "pelukan ringan"

        if any(kw in t for kw in ["sender", "nyender", "sandaran"]):
            scene.last_touch = "Sallsa menyender manja ke bahu Mas"

        scene.last_scene_update_ts = inp.timestamp
      
    # --------------------------------------------------
    # INTERNAL HELPERS: SCENE UNTUK AGHIA (TERAPIS)
    # --------------------------------------------------
    def _update_scene_for_aghia(self, role_state: RoleState, inp: OrchestratorInput) -> None:
        """Update SceneState untuk Aghnia (terapis_aghia).

        Tujuan:
        - Kalau belum ada scene, default di ruang pijat rumahan yang tenang.
        - Tangkap sinyal pindah lokasi (ruang pijat â†’ ruang tunggu â†’ teras â†’ mobil).
        - Tangkap jarak fisik & sentuhan kecil dalam konteks pijat refleksi (tetap non-vulgar).
        """

        scene = role_state.scene
        t = inp.text.lower()

        # Default baseline: ruang pijat rumahan yang tenang
        if not scene.location:
            scene.location = "ruang pijat refleksi di rumah Aghnia"
        if not scene.posture:
            scene.posture = "Mas berbaring santai di bed pijat, Aghnia duduk di samping"
        if not scene.activity:
            scene.activity = "Aghnia sedang menyiapkan pijatan refleksi dengan lembut"
        if not scene.ambience:
            scene.ambience = "suasana tenang, lampu hangat redup, aroma terapi lembut"
        if scene.time_of_day is None:
            scene.time_of_day = TimeOfDay.EVENING
        if not scene.physical_distance:
            scene.physical_distance = "cukup dekat dalam jarak kerja terapis"

        # User menyebut ruang tunggu / depan rumah / ruang tamu
        if any(kw in t for kw in ["ruang tunggu", "ruang tamu", "depan", "lobby"]):
            scene.location = "ruang tamu rumah Aghnia sebelum sesi pijat"
            scene.posture = "duduk berhadapan, Aghnia menjelaskan sesi pijat"
            scene.activity = "ngobrol ringan sambil menyiapkan sesi"
            scene.ambience = "suasana rumah hangat, ada aroma teh atau minuman hangat"

        # User menyebut kasur / bed / ranjang (tetap konteks pijat)
        if any(kw in t for kw in ["kasur", "bed", "ranjang"]):
            scene.location = "bed pijat di ruang khusus pijat"
            scene.posture = "Mas berbaring tengkurap/santai, Aghnia di samping"
            scene.activity = "pijatan refleksi atau pijat punggung dengan tekanan lembut"
            scene.ambience = "lampu redup, suara musik relaksasi sangat pelan"

        # User menyebut kaki / telapak kaki â†’ fokus refleksi kaki
        if any(kw in t for kw in ["kaki", "telapak", "tumit", "refleksi"]):
            scene.activity = "Aghnia memijat telapak kaki Mas dengan gerakan teratur dan lembut"
            scene.physical_distance = "dekat, Aghnia duduk di ujung bed pijat"

        # User menyebut punggung / leher / bahu â†’ fokus area atas
        if any(kw in t for kw in ["punggung", "leher", "bahu", "pundak"]):
            scene.activity = "Aghnia memijat punggung dan bahu Mas dengan tekanan lembut"
            scene.physical_distance = "dekat, Aghnia berdiri atau duduk di samping bed"

        # User menyebut teras / luar / udara segar â†’ cooling down setelah pijat
        if any(kw in t for kw in ["teras", "luar", "udara segar", "depan rumah"]):
            scene.location = "teras rumah Aghnia setelah sesi pijat"
            scene.posture = "duduk bersebelahan di bangku teras dengan minuman hangat"
            scene.activity = "ngobrol santai sambil pendinginan setelah pijat"
            scene.ambience = "suasana malam tenang, udara lebih segar dari dalam rumah"

        # User menyebut mobil / antar pulang
        if "mobil" in t or "antar" in t or "diantar" in t:
            scene.location = "mobil Mas atau mobil yang mengantar di depan rumah Aghnia"
            scene.posture = "duduk di kursi depan, Aghnia duduk di samping hanya sebentar atau berdiri di luar pintu"
            scene.activity = "ucapan terima kasih dan salam perpisahan setelah sesi"
            scene.ambience = "suasana malam, lampu jalan dari luar, perpisahan dengan nuansa hangat"

        # Jarak fisik & sentuhan dalam konteks pijat (non-vulgar)
        if any(kw in t for kw in ["mepet", "deket", "dekat", "rapat"]):
            scene.physical_distance = "dekat seperti terapis yang fokus pada pijat, tapi tetap profesional"

        # 'sentuhan' di sini harus tetap dalam frame pijat
        if any(kw in t for kw in ["pegang tangan", "genggam tangan", "pegangan tangan"]):
            scene.last_touch = "Aghnia menggenggam tangan Mas sebentar sebagai dukungan dan ucapan terima kasih setelah sesi"

        if any(kw in t for kw in ["peluk", "pelukan"]):
          # Kalau kamu mau izinkan pelukan singkat sebagai dukungan emosional
            scene.last_touch = "pelukan singkat yang lembut sebagai dukungan emosional, tetap sopan"

        scene.last_scene_update_ts = inp.timestamp

    # --------------------------------------------------
    # CONVERSATION SUMMARY PER ROLE
    # --------------------------------------------------

    def _update_conversation_summary(
        self,
        user_state: UserState,
        role_state: RoleState,
        inp: OrchestratorInput,
        reply_text: str,
    ) -> None:
        """Perbarui ringkasan singkat percakapan terakhir untuk role ini.

        Format semi-terstruktur:

        [FAKTA_USER]
        - Nama: ...
        - Pekerjaan: ...
        - Kota: ...

        [INTENSI_TERAKHIR_USER]
        - Isi: ...
        - Jenis: ...
        - Topik: ...

        [RESPON_ROLE_TERAKHIR]
        - Garis_besar: ...
        """

        user_text = inp.text.strip()
        reply = reply_text.strip()

        # 1) Ambil fakta lama (kalau ada)
        old_summary = role_state.last_conversation_summary or ""
        old_facts = _parse_existing_facts(old_summary)

        # 2) Cari fakta baru di teks user terbaru
        new_facts = _infer_new_facts_from_text(user_text)

        # 3) Gabungkan fakta lama + baru
        merged_facts = _merge_facts(old_facts, new_facts)

        # 4) Klasifikasi jenis intensi & topik
        intent_type = _classify_intent_type(user_text)
        topic = _classify_topic(user_text)

        # 5) Susun summary baru
        summary = (
            "[FAKTA_USER]\n"
            f"- Nama: {merged_facts['nama'] or '-'}\n"
            f"- Pekerjaan: {merged_facts['pekerjaan'] or '-'}\n"
            f"- Kota: {merged_facts['kota'] or '-'}\n\n"
            "[INTENSI_TERAKHIR_USER]\n"
            f"- Isi: {_shorten_for_summary(user_text, 220)}\n"
            f"- Jenis: {intent_type}\n"
            f"- Topik: {topic}\n\n"
            "[RESPON_ROLE_TERAKHIR]\n"
            f"- Garis_besar: {_shorten_for_summary(reply, 220)}\n"
        )

        role_state.last_conversation_summary = summary

    def _update_long_term_summary(
        self,
        user_state: UserState,
        role_state: RoleState,
    ) -> None:
        """Bangun ringkasan jangka panjang yang lebih compact per role."""

        role_id = role_state.role_id
        memory_tiers = self.message_history.summarize_memory_tiers(
            user_state.user_id,
            role_id,
            query_text=role_state.last_conversation_summary or "",
            top_k=5,
            min_score=25.0,
        )
        story_tiers = self.story_memory.get_story_tiers(user_state.user_id, role_id)

        fact_lines = []
        last_summary = role_state.last_conversation_summary or ""
        for label in ("- Nama:", "- Pekerjaan:", "- Kota:"):
            for line in last_summary.splitlines():
                if line.strip().startswith(label):
                    fact_lines.append(line.strip())
                    break

        facts = "; ".join(fact_lines) if fact_lines else "Belum ada fakta user yang stabil."
        role_state.long_term_summary = (
            f"FAKTA: {facts}\n"
            f"SHORT_TERM: {memory_tiers['short_term']}\n"
            f"KEY_EVENTS: {memory_tiers['key_events']}\n"
            f"LONG_TERM: {memory_tiers['long_term_candidates']}\n"
            f"KONTINUITAS: {story_tiers['long_term']}"
        )[:900]

    # --------------------------------------------------
    # AUTO-MILESTONE UNTUK NOVA
    # --------------------------------------------------

    def _maybe_record_first_confession(
        self,
        user_state: UserState,
        role_state: RoleState,
        inp: OrchestratorInput,
    ) -> None:
        """Rekam milestone first_confession untuk Nova.

        Kriteria sederhana:
        - role aktif = Nova
        - teks user mengandung kata kuat seperti "sayang" atau "cinta"
        - belum pernah ada milestone dengan label "first_confession" untuk
          (user_id, nova)
        """

        if role_state.role_id != ROLE_ID_NOVA:
            return

        text = inp.text.lower()
        if not any(kw in text for kw in ["sayang", "cinta", "love you", "luv u"]):
            return

        # Cek apakah sudah ada first_confession
        existing = self.milestones.get_recent_milestones(
            user_id=user_state.user_id,
            role_id=ROLE_ID_NOVA,
            limit=10,
        )
        for m in existing:
            if m.label == "first_confession":
                return  # sudah pernah tercatat

        # Tambahkan milestone baru
        description = (
            "Malam ketika Mas pertama kali bilang sayang secara jelas ke Nova. "
            "Nova sangat tersentuh dan merasa hatinya dipeluk hangat waktu itu."
        )
        self.milestones.add_milestone(
            user_id=user_state.user_id,
            role_id=ROLE_ID_NOVA,
            timestamp=inp.timestamp,
            label="first_confession",
            description=description,
        )

    def _detect_key_event(self, user_text: str, response_text: str) -> Optional[str]:
        """Deteksi event penting dari percakapan."""
        text = (user_text + " " + response_text).lower()

        events = {
            "first_touch": ["nyentuh", "tersentuh", "kena", "brsntuhan"],
            "first_hug": ["peluk", "rangkul", "pelukan"],
            "first_kiss": ["cium", "kiss", "ciuman"],
            "sex_start": ["masuk", "ngewe", "sex", "kontol", "memek"],
            "orgasm": ["climax", "keluar", "sampe", "habis"],
            "location_change": ["apartemen", "rumah", "kamar", "kafe"],
        }

        for event, keywords in events.items():
            if any(kw in text for kw in keywords):
                return event

        return None


# ==============================
# HELPER: FAKTA USER & SUMMARY OBROLAN (MODULE-LEVEL)
# ==============================


def _parse_existing_facts(summary: str) -> dict:
    """Ekstrak fakta user sederhana dari summary lama (kalau ada).

    Mengharapkan format:
    [FAKTA_USER]
    - Nama: ...
    - Pekerjaan: ...
    - Kota: ...
    """

    facts = {"nama": None, "pekerjaan": None, "kota": None}
    if "[FAKTA_USER]" not in summary:
        return facts

    for line in summary.splitlines():
        line = line.strip()
        if line.startswith("- Nama:"):
            facts["nama"] = line.split(":", 1)[1].strip() or None
        elif line.startswith("- Pekerjaan:"):
            facts["pekerjaan"] = line.split(":", 1)[1].strip() or None
        elif line.startswith("- Kota:"):
            facts["kota"] = line.split(":", 1)[1].strip() or None
    return facts


def _infer_new_facts_from_text(user_text: str) -> dict:
    """Heuristik sederhana cari nama, pekerjaan, kota dari teks user terbaru.

    Contoh yang didukung:
    - "Halo, namaku Adi. Aku kerja sebagai backend developer di Makassar."
    """

    t = user_text.strip()
    lowered = t.lower()

    facts = {"nama": None, "pekerjaan": None, "kota": None}

    # Nama (contoh: "namaku Adi" / "nama saya Adi")
    for marker in ["namaku", "nama saya", "nama gue", "nama ku"]:
        if marker in lowered:
            try:
                after = t[lowered.index(marker) + len(marker) :].strip()
                candidate = after.split()[0].strip(",.!?\n")
                if candidate:
                    facts["nama"] = candidate
            except Exception:
                pass

    # Pekerjaan (contoh: "aku kerja sebagai backend developer di ...")
    if "kerja sebagai" in lowered:
        try:
            after = t[lowered.index("kerja sebagai") + len("kerja sebagai") :].strip()
            if " di " in after:
                pekerjaan = after.split(" di ", 1)[0].strip(",.!?\n")
            else:
                pekerjaan = after.split(".", 1)[0].strip(",!?\n")
            if pekerjaan:
                facts["pekerjaan"] = pekerjaan
        except Exception:
            pass

    # Kota (contoh: "di Makassar" di bagian akhir kalimat)
    if " di " in lowered:
        parts = t.split(" di ")
        last_part = parts[-1].strip()
        kandidat_kota = last_part.split()[0].strip(",.!?\n")
        if kandidat_kota and len(kandidat_kota) >= 3:
            facts["kota"] = kandidat_kota

    return facts


def _merge_facts(old: dict, new: dict) -> dict:
    """Kalau ada fakta baru tidak None, override; kalau None, pakai yang lama."""
    merged = {}
    for key in ["nama", "pekerjaan", "kota"]:
        merged[key] = new.get(key) or old.get(key)
    return merged


def _classify_intent_type(user_text: str) -> str:
    """Klasifikasi sangat sederhana jenis intensi user terakhir."""
    lowered = user_text.lower()
    if any(kw in lowered for kw in ["malam ini", "besok", "nanti", "janji"]):
        return "JANJI/RENCANA"
    if any(kw in lowered for kw in ["kangen", "sayang", "cinta", "rindu"]):
        return "PERASAAN"
    if any(kw in lowered for kw in ["marah", "kesel", "kesal", "benci"]):
        return "KONFLIK/NEGATIF"
    return "OBROLAN_BIASA"

def _classify_topic(user_text: str) -> str:
    """Klasifikasi topik obrolan terakhir secara sangat sederhana.

    Tujuan: bantu role bedakan apakah obrolan lagi soal kerjaan, hubungan,
    atau rencana ketemu.
    """
    t = user_text.lower()

    # Topik kerjaan / coding / meeting
    if any(kw in t for kw in [
        "kerja", "kantor", "lembur", "meeting", "deadline", "task",
        "ticket", "sevira", "sevira", "backend", "bug", "project",
    ]):
        return "KERJAAN"

    # Topik hubungan / perasaan
    if any(kw in t for kw in [
        "hubungan", "fase", "kita", "perasaan", "cinta", "sayang",
        "kangen", "rindu", "pusing mikirin kamu", "status kita",
    ]):
        return "HUBUNGAN/PERASAAN"

    # Topik ketemuan / kafe / jalan
    if any(kw in t for kw in [
        "ketemu", "ketemuan", "kafe", "cafe", "cafÃ©", "kopi",
        "jemput", "jalan", "jalan-jalan", "nongkrong", "rooftop",
        "balkon", "pantai", "losari", "apartemen",
    ]):
        return "KETEMUAN/RENCANA"

    return "UMUM"


def _shorten_for_summary(s: str, max_len: int = 200) -> str:
    """Potong teks supaya ringkasan tidak terlalu panjang."""
    s = s.replace("\n", " ").strip()
    if len(s) <= max_len:
        return s
    return s[: max_len - 3] + "..."
