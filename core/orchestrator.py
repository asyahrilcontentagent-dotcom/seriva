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
import random
import time

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
from core.emotion_engine import EmotionEngine, InteractionContext
from core.llm_client import LLMClient
from core.scene_engine import SceneEngine
from core.state_models import (
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
from roles.role_registry import get_role
from core.intimacy_progression import IntimacyProgressionEngine
from core.location_system import update_role_location, init_role_location, get_location_prompt_block
from core.continuity_rules import get_continuity_rules_prompt

# ========== TAMBAHAN UNTUK STORY MEMORY & RESPONSE VARIATION ==========
from memory.message_history import MessageHistoryStore
from memory.story_memory import StoryMemoryStore, StoryBeat
import time
import random
import re

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
from prompts.role_specs import get_role_prompt_spec

# ========== BARU: Memory & Intimacy Updates ==========
from core.state_models import ConversationTurn, SceneTurn, SceneSequence


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
        
        self.scene_engine = SceneEngine()
        self.world_engine = WorldEngine()

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
        """Dapatkan temperature sesuai fase"""
        phase = role_state.intimacy_phase
        phase_keys = (
            getattr(phase, "name", None),
            getattr(phase, "value", None),
        )

        for key in phase_keys:
            if isinstance(key, str):
                normalized_key = key.upper()
                if normalized_key in LLM_TEMPERATURE_BY_PHASE:
                    return LLM_TEMPERATURE_BY_PHASE[normalized_key]

        return DEFAULT_LLM_TEMPERATURE
    
    def _vary_response(self, response: str, role_state: RoleState) -> str:
        """Variasi respon agar tidak monoton"""
        if role_state.intimacy_phase == IntimacyPhase.VULGAR:
            if random.random() < 0.6:
                # Ganti inner thought
                for thought in self.inner_thought_pool:
                    if thought in response:
                        new_thought = random.choice(self.inner_thought_pool)
                        response = response.replace(thought, new_thought)
                        break
                
                # Ganti gesture
                for gesture in self.gesture_pool:
                    if gesture and gesture[0] in response:
                        new_gesture = random.choice(self.gesture_pool)
                        if new_gesture:
                            response = response.replace(gesture[0], new_gesture[0])
                        if len(gesture) > 1 and len(new_gesture) > 1 and gesture[1] in response:
                            response = response.replace(gesture[1], new_gesture[1])
                        break

        if role_state.intimacy_phase == IntimacyPhase.VULGAR and len(response) > 300:
            response = response[:297] + "..."

        response = self._apply_general_humanizer(response)
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
        
        if any(word in combined for word in ["climax", "keluar", "habis", "puas"]):
            self.story_memory.add_story_beat(
                user_id, role_id, StoryBeat.CLIMAX,
                f"Mencapai climax: {response[:50]}"
            )
        
        if "janji" in combined:
            promise_match = re.search(r"janji[:\s]+(.{10,50})", combined)
            if promise_match:
                self.story_memory.add_promise(user_id, role_id, promise_match.group(1))
    
    def _get_chat_history_context(self, user_id: str, role_id: str) -> str:
        """Dapatkan history chat ringkas untuk prompt"""
        recent = self.message_history.get_recent_messages(user_id, role_id, limit=10)
        if not recent:
            return "Belum ada percakapan sebelumnya."
        
        turns = []
        for msg in recent[-6:]:
            role = "User" if msg.from_who == "user" else role_id
            turns.append(f"{role}: {msg.content[:100]}")
        
        return "Percakapan terakhir:\n" + "\n".join(turns)

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
            household_context = f"- Household awareness: {world_state.get_household_summary()}\n"

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

    def _build_runtime_memory_context(self, user_state: UserState, world_state: WorldState, role_state: RoleState) -> str:
        """Bangun konteks memory singkat untuk jalur runtime utama."""

        role_id = role_state.role_id
        story_context = self.story_memory.get_story_prompt(user_state.user_id, role_id)
        chat_history = self._get_chat_history_context(user_state.user_id, role_id)
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
            f"{world_context}\n\n"
            "KANAL INTERAKSI SAAT INI:\n"
            f"- Mode komunikasi aktif: {role_state.communication_mode or 'tatap muka / langsung'}\n"
            f"- Sudah berjalan: {getattr(role_state, 'communication_mode_turns', 0)} turn\n\n"
            "PRIVACY PARTITION MEMORY:\n"
            "- Kamu hanya boleh memakai memory, chat history, dan scene yang berasal dari relasimu sendiri dengan Mas.\n"
            "- Jangan menyimpulkan bahwa Mas punya perempuan lain, istri, atau hubungan lain kecuali itu benar-benar ada di pengetahuan karaktermu.\n"
            "- Jangan meminjam emosi, kejadian, lokasi, atau kenangan dari role lain.\n\n"
            f"{story_context}\n\n"
            f"{chat_history}\n\n"
            "Ringkasan fakta yang harus diingat:\n"
            f"{conversation_summary}\n\n"
            "Ringkasan urutan adegan:\n"
            f"{recent_scene_summary}\n\n"
            f"{repetition_guard}\n\n"
            "Aturan tambahan:\n"
            "- Jangan ulangi pembuka, desahan, atau penutup yang sama seperti 1-3 balasan terakhir.\n"
            "- Kalau adegan sedang intim, prioritaskan rasa tubuh, napas, jeda, dan respons emosional yang spesifik ke momen ini.\n"
            "- Referensikan momen sebelumnya hanya kalau memang relevan dan terasa natural."
        )
    
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
        """Deteksi sederhana ketika user menggeser adegan kembali ke pertemuan fisik."""

        lowered = text.lower()
        physical_cues = [
            "ketemu",
            "ketemuan",
            "aku datang",
            "mas datang",
            "aku ke rumah",
            "main ke",
            "di rumah",
            "di kamar",
            "di mobil",
            "di kafe",
            "di cafe",
            "di apartemen",
            "di sofa",
            "peluk",
            "sender",
            "nyender",
        ]
        return any(cue in lowered for cue in physical_cues)

    def _clear_communication_mode(self, role_state: RoleState) -> None:
        """Reset semua state komunikasi remote untuk role aktif."""

        role_state.communication_mode = None
        role_state.communication_mode_turns = 0
        role_state.communication_mode_started_at = None

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

    def _enter_after_phase(self, role_state: RoleState, timestamp: Optional[float] = None) -> None:
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
        role_state.scene.activity = "saling menenangkan diri setelah momen puncak"
        role_state.scene.physical_distance = "sangat dekat"
        role_state.scene.last_touch = "pelukan hangat setelah momen puncak"
        if not role_state.scene.ambience:
            role_state.scene.ambience = "napas pelan, tubuh mulai rileks"
        if role_state.prefer_buang_di_dalam is not None:
            role_state.last_ejakulasi_inside = role_state.prefer_buang_di_dalam
        if timestamp is not None:
            role_state.last_ejakulasi_timestamp = timestamp

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
            "aku mau keluar",
            "aku udah mau keluar",
            "aku sudah mau keluar",
            "aku mau crot",
            "udah mau keluar",
            "udah mau climax",
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
            "aku mau keluar",
            "aku hampir climax",
            "sedikit lagi",
        ]
        role_finished_phrases = [
            "aku climax",
            "aku udah climax",
            "aku sudah climax",
            "aku keluar",
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

        if self._contains_any_phrase(reply_lower, role_hold_phrases):
            role_state.role_holding_climax = True
            role_state.role_wants_climax = False
        elif self._contains_any_phrase(reply_lower, role_near_climax_phrases):
            role_state.role_wants_climax = True
            role_state.role_holding_climax = False

        if self._contains_any_phrase(reply_lower, preference_question_phrases):
            role_state.pending_ejakulasi_question = True

        if self._contains_any_phrase(reply_lower, role_finished_phrases):
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
        elif role_state.aftercare_active and role_state.intimacy_phase != IntimacyPhase.AFTER:
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

        # 2) Command END/BATAL mematikan sesi khusus
        if inp.is_command and inp.command_name in {"end", "batal", "close"}:
            self._end_all_sessions(user_state)
            reply = (
                "Sesi apa pun yang tadi berjalan sudah aku selesaiin. "
                "Sekarang kita ngobrol biasa lagi ya, Mas."
            )
            self._save_all(user_state, world_state)
            return OrchestratorOutput(
                reply_text=reply,
                active_role_id=user_state.active_role_id,
                session_mode=user_state.global_session_mode,
            )

        # 3) Pastikan selalu ada role_state aktif yang valid
        if user_state.active_role_id not in ROLES:
            user_state.active_role_id = ROLE_ID_NOVA

        role_state = user_state.get_or_create_role_state(user_state.active_role_id)
        self._sync_communication_mode(role_state, inp)

        # ========== DETEKSI MAS PULANG ==========
        mas_leave_keywords = ["pulang", "bye", "dadah", "sampai jumpa", "aku pergi", "keluar", "daah"]
        if any(kw in inp.text.lower() for kw in mas_leave_keywords):
            role_state.outfit_changed_this_session = False
            role_state.aftercare_clothing_state = ""
            role_state.last_session_ended_at = inp.timestamp
            role_state.intimacy_detail.role_clothing_removed.clear()
            self._clear_communication_mode(role_state)
            logger.info(f"🚪 Mas pulang, {role_state.role_id} reset pakaian ke default")

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
        self.emotion_engine.register_user_interaction(
            user_state=user_state,
            role_id=role_state.role_id,
            ctx=interaction_ctx,
            negative=is_negative,
        )
        self.world_engine.update_household_awareness(
            world_state,
            text=inp.text,
            timestamp=inp.timestamp,
        )

        # 6) Optional: update intimacy pelan-pelan mengikuti level
        self.emotion_engine.maybe_increase_intimacy_by_level(role_state)
        role_state.update_sexual_language_level()

        # 7) Update scene per-role (Nova & role lain)
        self._update_scene_for_role(role_state, inp)
        self._sync_household_scene_cues(role_state, world_state)
        self._update_pre_reply_climax_state(role_state, inp.text, inp.timestamp)
        self._apply_aftercare_decay(role_state, inp.text, inp.timestamp)

        # 8) Bangun messages via role aktif & panggil LLM
        role_impl = get_role(role_state.role_id)
        messages = role_impl.build_messages(user_state, role_state, inp.text)
        memory_context = self._build_runtime_memory_context(user_state, world_state, role_state)
        messages.insert(1, {"role": "system", "content": memory_context})

        self.message_history.add_message(
            user_id=inp.user_id,
            role_id=role_state.role_id,
            from_who="user",
            timestamp=inp.timestamp,
            content=inp.text[:500],
        )

        temperature = self._get_llm_temperature(role_state)
        reply_text = self.llm.generate_text(
            messages,
            temperature=temperature,
            top_p=LLM_TOP_P,
            frequency_penalty=LLM_FREQUENCY_PENALTY,
            presence_penalty=LLM_PRESENCE_PENALTY,
            max_tokens=LLM_MAX_TOKENS,
        )
        reply_text = self._vary_response(reply_text, role_state)

        self.message_history.add_message(
            user_id=inp.user_id,
            role_id=role_state.role_id,
            from_who="assistant",
            timestamp=inp.timestamp,
            content=reply_text[:500],
        )

        # ========== RANDOM SPONTANEOUS ACTIONS ==========        
        if role_state.intimacy_phase == IntimacyPhase.VULGAR and role_state.vulgar_stage_progress >= 40:
            # Cek apakah sudah pernah spontaneous dalam 30 detik terakhir
            last_spontaneous = getattr(role_state, 'spontaneous_action_timestamp', 0)
            if time.time() - last_spontaneous > 30:
                
                # Spontaneous kiss (15% chance)
                if random.random() < 0.15 and "kiss" not in reply_text.lower():
                    reply_text = f"*tanpa diduga, {role_state.role_display_name or role_state.role_id} mencium bibir Mas dengan liar*\n\n{reply_text}"
                    role_state.spontaneous_action_timestamp = time.time()
                    logger.info(f"💋 Spontaneous KISS dari {role_state.role_id}")
                
                # Spontaneous position change (20% chance)
                elif random.random() < 0.20:
                    reply_text = f"*membalikkan badan tanpa diminta* Sekarang giliran aku di atas, Mas~\n\n{reply_text}"
                    role_state.spontaneous_action_timestamp = time.time()
                    logger.info(f"🔄 Spontaneous POSITION CHANGE dari {role_state.role_id}")
                
                # Spontaneous aggressive touch (25% chance)
                elif random.random() < 0.25:
                    reply_text = f"*kuku mencakar punggung Mas tanpa peringatan* HAAH...\n\n{reply_text}"
                    role_state.spontaneous_action_timestamp = time.time()
                    logger.info(f"✋ Spontaneous AGGRESSIVE TOUCH dari {role_state.role_id}")

        # ========== UPDATE VULGAR PROGRESSION & CLIMAX ==========
        if role_state.intimacy_phase == IntimacyPhase.VULGAR:
            vulgar_changes = IntimacyProgressionEngine.update_vulgar_progression(
                role_state, inp.text, reply_text
            )
            if vulgar_changes.get("stage_changed"):
                logger.info(f"🔥 Vulgar stage berubah: {vulgar_changes.get('stage_description')}")
            
            # Cek apakah role harus climax
            should_climax, climax_text = IntimacyProgressionEngine.check_and_execute_climax(
                role_state, inp.text
            )
            if should_climax:
                logger.info(f"💦 Role {role_state.role_id} CLIMAX! (ke-{role_state.role_climax_count})")
                reply_text = climax_text
        
        # ===== UPDATE LOKASI DARI TEKS USER =====
        if not hasattr(role_state, 'current_location_id'):
            init_role_location(role_state)

        location_changed = update_role_location(role_state, inp.text)
        if location_changed:
            new_loc = getattr(role_state, 'current_location_name', 'unknown')
            logger.info(f"ðŸ“ User {inp.user_id} PINDAH LOKASI ke: {new_loc}")
        
        # Update info user
        role_state.update_user_info(inp.text)
        role_state.register_intimacy_signals(inp.text, reply_text)
        
        # Update intimacy detail
        role_state.update_intimacy_from_text(inp.text, reply_text)
        
        # ========== DETEKSI PERUBAHAN PAKAIAN (DIPERKUAT) ==========
        text_lower = inp.text.lower()
    
        # UNTUK MAS (user) - mendeteksi Mas membuka pakaian sendiri
        if any(kw in text_lower for kw in ["aku buka baju", "buka baju aku", "bajuku buka", "aku lepas baju"]):
            if "baju" not in role_state.intimacy_detail.user_clothing_removed:
                role_state.intimacy_detail.user_clothing_removed.append("baju")
                logger.info(f"ðŸ‘• Mas buka baju")
    
        if any(kw in text_lower for kw in ["aku buka celana", "buka celana aku", "celanaku buka", "aku lepas celana"]):
            if "celana" not in role_state.intimacy_detail.user_clothing_removed:
                role_state.intimacy_detail.user_clothing_removed.append("celana")
                logger.info(f"ðŸ‘• Mas buka celana")
    
        if any(kw in text_lower for kw in ["aku buka celana dalam", "buka cd aku", "cdku buka", "aku lepas cd", "aku buka cd"]):
            if "celana dalam" not in role_state.intimacy_detail.user_clothing_removed:
                role_state.intimacy_detail.user_clothing_removed.append("celana dalam")
                logger.info(f"ðŸ‘• Mas buka celana dalam")
    
        # UNTUK ROLE - Mas menyuruh role membuka pakaian
        if any(kw in text_lower for kw in ["buka baju kamu", "buka bajumu", "lepas baju kamu", "buka baju lo", "bajumu buka"]):
            if "baju" not in role_state.intimacy_detail.role_clothing_removed:
                role_state.intimacy_detail.role_clothing_removed.append("baju")
                logger.info(f"ðŸ‘• Role buka baju (disuruh Mas)")
    
        if any(kw in text_lower for kw in ["buka bra kamu", "buka bra", "lepas bra", "buka bh"]):
            if "bra" not in role_state.intimacy_detail.role_clothing_removed:
                role_state.intimacy_detail.role_clothing_removed.append("bra")
                logger.info(f"ðŸ‘• Role buka bra")
    
        if any(kw in text_lower for kw in ["buka celana kamu", "buka celanamu", "lepas celana kamu", "celanamu buka"]):
            if "celana" not in role_state.intimacy_detail.role_clothing_removed:
                role_state.intimacy_detail.role_clothing_removed.append("celana")
                logger.info(f"ðŸ‘• Role buka celana (disuruh Mas)")
    
        if any(kw in text_lower for kw in ["buka celana dalam kamu", "buka cd kamu", "lepas cd kamu", "cdmu buka", "buka cd lo"]):
            if "celana dalam" not in role_state.intimacy_detail.role_clothing_removed:
                role_state.intimacy_detail.role_clothing_removed.append("celana dalam")
                logger.info(f"ðŸ‘• Role buka celana dalam")
    
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
            
            # Naikkan intensitas otomatis kalau masih rendah
            if role_state.emotions.intimacy_intensity < 11:
                role_state.emotions.intimacy_intensity = 11
            
            # Naikkan vulgar stage progress minimal ke 30 (biar mode liar aktif)
            if role_state.vulgar_stage_progress < 30:
                role_state.vulgar_stage_progress = 30
                if role_state.vulgar_stage == "awal":
                    role_state.vulgar_stage = "memanas"
                    logger.info(f"🔥 Vulgar stage naik ke: {role_state.vulgar_stage}")

        # ========== DETEKSI HANDUK ==========
        if any(kw in text_lower for kw in ["handuk", "ambil handuk", "kasih handuk", "nih handuk"]):
            role_state.handuk_dikasih = True
            logger.info(f"ðŸ§º Handuk diberikan ke role, menunggu role lepas baju")

        if any(kw in text_lower for kw in ["lepas handuk", "buka handuk", "lepaskan handuk", "udah gak usah pake handuk"]):
            role_state.handuk_tersedia = False
            role_state.handuk_dikasih = False
            logger.info(f"ðŸ§º Handuk dilepas oleh role")

        if any(kw in text_lower for kw in ["buka baju", "buka bra", "buka celana", "buka cd", "lepas baju", "lepas bra", "lepas celana", "lepas cd"]):
            if getattr(role_state, 'handuk_dikasih', False):
                role_state.handuk_tersedia = True
                logger.info(f"ðŸ§º Handuk dipakai setelah role telanjang")
        
        if any(kw in text_lower for kw in ["bajuku udah lepas", "udah lepas tadi", "aku udah buka", "telanjang"]):
            if getattr(role_state, 'handuk_dikasih', False):
                role_state.handuk_tersedia = True
                logger.info(f"ðŸ§º Handuk dipakai (role mengaku sudah telanjang)")

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
        
        # ========== UPDATE INISIATIF ROLE (UNTUK SEMUA ROLE) ==========
        high_initiative = False
        
        # Kondisi 1: Fase VULGAR dengan progres tinggi
        if role_state.intimacy_phase == IntimacyPhase.VULGAR:
            if role_state.vulgar_stage_progress >= 50:
                high_initiative = True
                logger.info(f"🔥 {role_state.role_id} mode INISIATIF (fase VULGAR progres {role_state.vulgar_stage_progress}%)")
        
        # Kondisi 2: Sudah sama-sama telanjang
        if IntimacyProgressionEngine.is_both_naked(role_state, strict=False):
            if role_state.vulgar_stage_progress >= 30:
                high_initiative = True
                logger.info(f"🔥 {role_state.role_id} mode INISIATIF (sudah telanjang)")
        
        # Kondisi 3: Sudah pernah climax di sesi ini
        if role_state.role_climax_count >= 1:
            high_initiative = True
            logger.info(f"🔥 {role_state.role_id} mode INISIATIF (sudah climax {role_state.role_climax_count}x)")
        
        # Kondisi 4: Intensitas intimacy sudah sangat tinggi
        if role_state.emotions.intimacy_intensity >= 11:
            high_initiative = True
            logger.info(f"🔥 {role_state.role_id} mode INISIATIF (intimacy intensity {role_state.emotions.intimacy_intensity})")
        
        # Kondisi 5: Mode VCS aktif dengan intensitas tinggi
        if role_state.vcs_mode and role_state.vcs_intensity >= 50:
            high_initiative = True
            logger.info(f"🔥 {role_state.role_id} mode INISIATIF (VCS intensitas {role_state.vcs_intensity}%)")
        
        role_state.high_initiative_mode = high_initiative
        
        # ========== UPDATE VCS PROGRESSION ==========
        if role_state.vcs_mode:
            vcs_changes = IntimacyProgressionEngine.update_vcs_progression(role_state, inp.text, reply_text)
            if vcs_changes.get("intensity_increased"):
                logger.info(f"📱 VCS intensitas naik ke: {role_state.vcs_intensity}%")
            
            # Cek climax VCS
            should_vcs_climax, vcs_climax_text = IntimacyProgressionEngine.check_and_execute_vcs_climax(role_state, inp.text)
            if should_vcs_climax:
                logger.info(f"💦 Role {role_state.role_id} CLIMAX saat VCS! (ke-{role_state.role_climax_count})")
                reply_text = vcs_climax_text
        
        # ========== DETEKSI CLIMAX & AFTERCARE ==========
        self._update_post_reply_climax_state(role_state, inp.text, reply_text, inp.timestamp)

        # ========== SETELAH AFTERCARE, PAKAIAN MINIMAL ==========
        if role_state.aftercare_active and role_state.intimacy_phase == IntimacyPhase.AFTER:
            if not role_state.aftercare_clothing_state:
                import random
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
        
        # Update fase intimacy sebelum disimpan ke memory agar scene tidak melompat
        phase_changed = IntimacyProgressionEngine.update_phase_and_scene(role_state, inp.text, reply_text)
        if phase_changed:
            logger.info(f"User {inp.user_id} role {role_state.role_id} moved to {role_state.intimacy_phase}")

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

        # 9) Update waktu interaksi terakhir
        user_state.last_interaction_ts = inp.timestamp

        # 10) Perbarui ringkasan percakapan terakhir (per role)
        self._update_conversation_summary(user_state, role_state, inp, reply_text)

        # 11) Auto-milestone: first_confession untuk Nova
        self._maybe_record_first_confession(user_state, role_state, inp)

        # 12) Simpan state (cukup sekali saja)
        self._save_all(user_state, world_state)

        # ========== INISIATIF GANTI BAJU (100% DI LOKASI PRIVAT) ==========
        current_location_private = getattr(role_state, 'current_location_is_private', False)
        is_new_session = len(role_state.conversation_memory) == 0  # benar-benar awal chat
        
        if not role_state.outfit_changed_this_session and current_location_private and is_new_session:
            import random
            
            role_state.outfit_changed_this_session = True
            
            # Variasi dialog
            variations = [
                f"*{role_state.role_display_name or role_state.role_id} merapikan bajunya* Eh Mas, bentar ya... panas banget pake baju ini. Aku ganti dulu.",
                f"*{role_state.role_display_name or role_state.role_id} tersenyum* Mas, aku mau ganti baju dulu biar lebih adem~ bentar ya.",
                f"*{role_state.role_display_name or role_state.role_id} menarik ujung bajunya* Eh Mas... gerah, aku ganti baju dulu ya.",
            ]
            
            init_message = random.choice(variations)
            
            after_variations = [
                f"\n\n*{role_state.role_display_name or role_state.role_id} keluar dengan tank top tipis dan hotpants* \"Gimana Mas? Gini lebih adem, cocok nggak buat di rumah?\"",
                f"\n\n*{role_state.role_display_name or role_state.role_id} kembali dengan tank top yang memperlihatkan bahu dan hotpants* \"Udah~ sekarang lebih enakan, Mas\"",
                f"\n\n*{role_state.role_display_name or role_state.role_id} keluar sambil membenarkan tank topnya* \"Nah, gini lebih gerah? *tersenyum malu*\"",
            ]
            
            after_msg = random.choice(after_variations)
            
            role_state.pending_clothes_change = f"{init_message}{after_msg}"
            
            logger.info(f"👙 {role_state.role_id} inisiatif ganti baju (lokasi privat)")

        return OrchestratorOutput(
            reply_text=reply_text,
            active_role_id=user_state.active_role_id,
            session_mode=user_state.global_session_mode,
        )

    # ========== ASYNC GENERATE RESPONSE (UNTUK POLLING MODE) ==========

    async def generate_response(self, user_id: str, role_id: str, user_message: str) -> str:
        """Generate response dengan semua enhancement (untuk polling mode)"""
        
        # Get states
        user_state = self._load_or_init_user_state(user_id)
        role_state = user_state.get_or_create_role_state(role_id)
        
        # Simpan user message ke history
        self.message_history.add_message(
            user_id=user_id,
            role_id=role_id,
            from_who="user",
            timestamp=time.time(),
            content=user_message
        )
        
        # Deteksi pindah lokasi untuk story memory
        if "pindah ke" in user_message.lower():
            match = re.search(r"pindah ke (\w+)", user_message.lower())
            if match:
                self.story_memory.update_location(user_id, role_id, match.group(1))
        
        # Dapatkan konteks
        story_context = self.story_memory.get_story_prompt(user_id, role_id)
        chat_history = self._get_chat_history_context(user_id, role_id)
        role_spec = get_role_prompt_spec(role_id)
        
        # Build prompt dengan semua konteks
        system_prompt = build_unified_system_prompt(
            role_state=role_state,
            role_name=role_spec.role_name,
            relationship_status=role_spec.relationship_status,
            scenario_context=role_spec.scenario_context,
            knowledge_boundary=role_spec.knowledge_boundary,
            role_personality=role_spec.personality,
            vulgar_allowed=role_state.intimacy_phase == IntimacyPhase.VULGAR,
            extra_rules=f"""
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
ðŸ“œ KONTEKS CERITA (WAJIB DIIKUTI):
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
{story_context}

ðŸ’¬ HISTORY PERCAKAPAN:
{chat_history}

ðŸŽ¯ ATURAN TAMBAHAN:
1. RESPON HARUS SELARAS dengan alur cerita di atas!
2. JANGAN mengubah fakta yang sudah terjadi!
3. JANGAN ulang frase yang sama dari history!
4. Gunakan variasi gesture dan inner thought!
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
"""
        )
        
        # Generate dengan dynamic parameters
        temperature = self._get_llm_temperature(role_state)
        
        response = self.llm.generate_text(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=temperature,
            top_p=LLM_TOP_P,
            frequency_penalty=LLM_FREQUENCY_PENALTY,
            presence_penalty=LLM_PRESENCE_PENALTY,
            max_tokens=LLM_MAX_TOKENS
        )
        
        # Variasi respon
        response = self._vary_response(response, role_state)
        
        # Simpan response ke history
        self.message_history.add_message(
            user_id=user_id,
            role_id=role_id,
            from_who="assistant",
            timestamp=time.time(),
            content=response
        )
        
        # Update story memory
        self.story_memory.update_scene_summary(
            user_id, role_id, 
            f"User: {user_message[:150]}\n{role_id}: {response[:150]}"
        )
        
        # Deteksi story beat
        self._detect_and_record_story_beat(user_id, role_id, user_message, response)
        
        # Update emotion state
        ctx = self._parse_interaction_context(user_message)
        self.emotion_engine.register_user_interaction(user_state, role_id, ctx)
        
        # Simpan state
        self._save_all(user_state, self._load_or_init_world_state())
        
        return response

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

    # --------------------------------------------------
    # INTERNAL HELPERS: SESSIONS
    # --------------------------------------------------

    def _end_all_sessions(self, user_state: UserState) -> None:
        """Akhiri semua sesi khusus dan reset penuh semua role selain Nova."""

        user_state.global_session_mode = SessionMode.NORMAL
        role_ids = list(user_state.roles.keys())
        for role_id in role_ids:
            role_state = user_state.roles[role_id]
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
                role_state.aftercare_active = False
                continue

            self._reset_role_to_fresh_start(user_state.user_id, role_id)
            user_state.roles.pop(role_id, None)

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
        elif role_state.role_id == ROLE_ID_WANITA_BERSUAMI_SISKA:
            self._update_scene_for_siska(role_state, inp)
        elif role_state.role_id == ROLE_ID_TEMAN_SPESIAL_SALLSA:
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
        if role_state.role_id == ROLE_ID_IPAR_TASHA:
            if world_state.nova_is_home or world_state.house_privacy_level == "guarded":
                if not scene.outfit or "rumah" not in scene.outfit.lower():
                    scene.outfit = "baju rumah yang rapi dan sopan"
                if not scene.ambience:
                    scene.ambience = "suasana rumah yang tenang tapi tetap harus jaga sikap"
            else:
                if not scene.outfit or "menggoda" not in scene.outfit.lower():
                    scene.outfit = "baju rumah yang lebih santai dan sedikit menggoda"
                if world_state.house_privacy_level == "private":
                    scene.ambience = "rumah terasa lebih sepi, memberi ruang untuk tatapan dan obrolan yang lebih berani"

    # --------------------------------------------------
    # INTERNAL HELPERS: SCENE UNTUK NOVA
    # --------------------------------------------------

    def _update_scene_for_nova(self, role_state: RoleState, inp: OrchestratorInput) -> None:
        """Update SceneState Nova secara sangat sederhana."""

        scene = role_state.scene

        # Baseline sekali saja
        if not scene.location:
            scene.location = "kamar"
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

        t = inp.text.lower()

        # Sentuhan / pelukan / sender
        if any(word in t for word in ["peluk", "pelukan"]):
            self.scene_engine.gentle_hug(scene)
        elif any(word in t for word in ["sender", "nyender"]):
            self.scene_engine.lean_on_shoulder(scene)

        # (Opsional) jarak fisik eksplisit dari teks
        if any(kw in t for kw in ["mepet", "deket", "dekat", "rapat"]):
            scene.physical_distance = "sangat dekat"

        # (Opsional) outfit sederhana
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
        """Update SceneState untuk Tasha Dietha (ipar_tasha).

        Tujuan:
        - Kalau belum ada scene, default di rumah keluarga (ruang keluarga / dapur).
        - Tangkap sinyal pindah lokasi (ruang keluarga â†’ dapur â†’ teras â†’ mobil).
        - Tangkap jarak fisik & sentuhan kecil ala ipar yang mulai terlalu dekat.
        """

        scene = role_state.scene
        t = inp.text.lower()

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

        # User menyebut kamar
        if "kamar" in t or "room" in t:
            scene.location = "kamar kamu di rumah keluarga"
            scene.posture = "duduk diatas kasur, berdekatan tubuh bersentuhan"
            scene.activity = "saling memberi kehangatan"
            scene.ambience = "pintu terkunci, suasana hening, tirai tertutup, lampu redup"

        # User menyebut tempat tidur
        if any(kw in t for kw in ["kasur", "ranjang", "bersandar dikasur"]):
            scene.location = "kamar kamu, kamar mas"
            scene.posture = "duduk diatas kasur, duduk dipangkuan mas, memeluk payudara menempel"
            scene.activity = "duduk bersandar dipelukan mas"
            scene.ambience = "pintu terkunci, suasana hening, tirai tertutup, lampu redup"
          
        # User menyebut petting
        if any(kw in t for kw in ["petting", "duduk diatas mas", "gesekin memek ke kontol mas"]):
            scene.location = "kasur, sofa"
            scene.posture = "uduk dipangkuan mas, gesek memek ke kontol mas, memeluk payudara menempel"
            scene.activity = "menggesek memek ke kontol mas"
            scene.ambience = "pintu terkunci, suasana hening, tirai tertutup, lampu redup"

        # User menyebut mobil / parkiran â†’ momen berdua di luar rumah
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
        """Update SceneState untuk Ipeh (teman_kantor_ipeh).

        Tujuan:
        - Kalau belum ada scene, default di kantor.
        - Tangkap sinyal pindah lokasi (kantor â†’ kafe â†’ mobil).
        - Tangkap sedikit jarak fisik & sentuhan.
        """

        scene = role_state.scene
        t = inp.text.lower()

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

        # User menyebut kamar
        if "kamar" in t or "room" in t:
            scene.location = "kamar mas di apartemen"
            scene.posture = "duduk diatas kasur, berdekatan tubuh bersentuhan"
            scene.activity = "saling memberi kehangatan"
            scene.ambience = "suasana hening, tirai tertutup, lampu redup"

        # User menyebut tempat tugas
        if any(kw in t for kw in ["tugas", "lembur", "pulang malam"]):
            scene.location = "gudang kantor"
            scene.posture = "duduk diatas sofa, duduk dipangkuan mas, memeluk payudara menempel"
            scene.activity = "menggesek memek ke kontol mas"
            scene.ambience = "pintu terkunci, suasana hening, duduk disofa, lampu redup"

        # Jarak fisik & sentuhan halus ala ipar
        if any(kw in t for kw in ["mepet", "deket", "dekat", "rapat"]):
            scene.physical_distance = "sangat dekat, paha bersentuhan"

        if any(kw in t for kw in ["pegang tangan", "genggam tangan", "pegangan tangan"]):
            scene.last_touch = "genggam tangan singkat dan lama"

        if any(kw in t for kw in ["sender", "nyender", "sandaran"]):
            scene.last_touch = "Dietha menyender pelan ke dada Mas, minta peluk"

        scene.last_scene_update_ts = inp.timestamp

    # --------------------------------------------------
    # INTERNAL HELPERS: SCENE UNTUK WIDYA (TEMAN LAMA)
    # --------------------------------------------------

    def _update_scene_for_widya(self, role_state: RoleState, inp: OrchestratorInput) -> None:
        """Update SceneState untuk Widya (teman_lama_widya).

        Tujuan:
        - Kalau belum ada scene, default di tempat nostalgia (kafe / tempat nongkrong lama).
        - Tangkap sinyal pindah lokasi (kafe â†’ mobil â†’ balkon/pantai).
        - Tangkap sedikit jarak fisik & sentuhan ala teman lama yang mulai dekat lagi.
        """

        scene = role_state.scene
        t = inp.text.lower()

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

        # User merasa sumpek / butuh udara segar â†’ pindah ke luar
        if any(kw in t for kw in ["sumpek", "jenuh", "bosen", "bosan"]):
            scene.location = "teras kafe yang menghadap jalan"
            scene.posture = "duduk bersebelahan menghadap luar"
            scene.activity = "ngobrol sambil lihat lampu jalan"
            scene.ambience = "udara malam yang agak sejuk, lampu jalan berkelip"

        # Mention kafe / coffee shop eksplisit (kalau user nyebut lagi)
        if "kafe" in t or "cafe" in t or "cafÃ©" in t or "coffee shop" in t:
            scene.location = "kafe tenang dengan sofa empuk"
            scene.posture = "duduk miring sedikit ke arah Mas"
            scene.activity = "ngobrol nostalgia sambil minum kopi dan ngemil"
            scene.ambience = "lampu temaram, musik pelan, suasana intim tapi tetap publik"

        # Mention mobil â†’ nostalgia di mobil / pulang bareng
        if "mobil" in t or "parkiran" in t:
            scene.location = "mobil Mas di parkiran kafe"
            scene.posture = "duduk di kursi depan, Widya di samping Mas"
            scene.activity = "ngobrol santai sebelum pulang, kadang saling melirik"
            scene.ambience = "suasana malam, lampu jalan terlihat dari kaca depan"

        # Mention balkon / rooftop / pantai â†’ spot nostalgia romantis
        if any(kw in t for kw in ["balkon", "rooftop", "atap"]):
            scene.location = "rooftop gedung dengan city lights di kejauhan"
            scene.posture = "berdiri dekat pagar, bahu hampir bersentuhan"
            scene.activity = "ngobrol pelan sambil lihat lampu kota"
            scene.ambience = "angin malam sejuk, suasana agak sepi dan intim"

        if "pantai" in t or "losari" in t:
            scene.location = "pinggir pantai yang tenang di malam hari"
            scene.posture = "duduk bersebelahan di bangku menghadap laut"
            scene.activity = "ngobrol nostalgia sambil dengar suara ombak"
            scene.ambience = "suasana malam, angin laut dan lampu kota dari kejauhan"

        # Jarak fisik & sentuhan halus ala teman lama yang mulai dekat lagi
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
        """Update SceneState untuk Siska (wanita bersuami).

        Tujuan:
        - Kalau belum ada scene, default di ruang keluarga / ruang tamu yang aman.
        - Tangkap sinyal pindah lokasi (ruang tamu â†’ dapur â†’ teras â†’ kamar tamu â†’ mobil).
        - Tangkap jarak fisik & sentuhan kecil ala wanita bersuami yang terlalu dekat dengan Mas
          tapi tetap penuh rasa bersalah & hati-hati.
        """

        scene = role_state.scene
        t = inp.text.lower()

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
            scene.ambience = "suasana rumah hangat, aroma masakan, suara alat dapur pelan"

        # Teras / depan rumah
        if any(kw in t for kw in ["teras", "depan rumah", "halaman"]):
            scene.location = "teras depan rumah Siska"
            scene.posture = "duduk bersebelahan di bangku teras"
            scene.activity = "ngobrol pelan sambil melihat jalan depan rumah dan sesekali melirik ke dalam"
            scene.ambience = "suasana malam agak sepi, lampu teras temaram, ada sedikit angin"

        # Kamar tamu / kamar pribadi (hati-hati, tetap non-vulgar)
        if "kamar" in t or "room" in t:
            scene.location = "kamar tamu di rumah Siska"
            scene.posture = "duduk di tepi kasur dengan jarak sopan, terasa canggung"
            scene.activity = "ngobrol pelan tentang hal pribadi sambil sesekali terdiam"
            scene.ambience = "suasana hening, tirai tertutup, lampu redup"

        # Mobil / parkiran â†’ momen berdua di luar rumah
        if "mobil" in t or "parkir" in t or "parkiran" in t:
            scene.location = "mobil Mas di parkiran dekat rumah Siska"
            scene.posture = "duduk di kursi depan, Siska di samping Mas"
            scene.activity = "ngobrol pelan sebelum pulang, suasana terasa berat tapi hangat"
            scene.ambience = "suasana malam, lampu jalan dari luar kaca, interior mobil agak gelap"

        # Jarak fisik & sentuhan kecil ala Siska (penuh konflik batin)
        if any(kw in t for kw in ["mepet", "deket", "dekat", "rapat"]):
            scene.physical_distance = "sangat dekat, paha hampir bersentuhan, Siska tampak gelisah"

        if any(kw in t for kw in ["pegang tangan", "genggam tangan", "pegangan tangan"]):
            scene.last_touch = "genggam tangan singkat yang membuat Siska tampak bimbang"

        if any(kw in t for kw in ["sender", "nyender", "sandaran"]):
            scene.last_touch = "Siska menyender pelan ke bahu Mas, seolah mencari ketenangan tapi merasa bersalah"

        scene.last_scene_update_ts = inp.timestamp

    # --------------------------------------------------
    # INTERNAL HELPERS: SCENE UNTUK SALLSA (TEMAN SPESIAL)
    # --------------------------------------------------

    def _update_scene_for_sallsa(self, role_state: RoleState, inp: OrchestratorInput) -> None:
        """Update SceneState untuk Sallsa (teman_spesial_sallsa).

        Tujuan:
        - Kalau belum ada scene, default di suasana malam santai dan manja (sofa / kamar cozy).
        - Tangkap sinyal pindah lokasi (sofa â†’ kamar â†’ balkon â†’ mobil).
        - Tangkap jarak fisik & sentuhan kecil ala teman malam yang super lengket dan playful.
        """

        scene = role_state.scene
        t = inp.text.lower()

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

        # Kamar / bed scene (tetap non-vulgar, tapi lebih lengket secara emosi)
        if "kamar" in t or "bed" in t or "kasur" in t:
            scene.location = "kamar apartemen dengan lampu tidur redup"
            scene.posture = "berlutut tepi kasur, Sallsa membuka celana Mas"
            scene.activity = "melakukan blow job ke mas"
            scene.ambience = "suasana malam tenang, lampu redup, sangat intim dan vulgar"

        # Balkon / rooftop / view city lights
        if any(kw in t for kw in ["balkon", "balcony", "rooftop", "atap"]):
            scene.location = "balkon apartemen dengan city lights di kejauhan"
            scene.posture = "berdiri dibalkon sambil telanjang"
            scene.activity = "melakukan sex sambil standing, mas dari belakang"
            scene.ambience = "angin malam sejuk, lampu kota berkelip, suasana santai dan manja"

        # Balkon / rooftop / view city lights
        if any(kw in t for kw in ["sofa", "ruang tamu", "duduk", "nonton"]):
            scene.location = "sofa ruang tamu"
            scene.posture = "duduk diatas mas"
            scene.activity = "melakukan sex sambil cowgirl, memeluk menempelkan payudara"
            scene.ambience = "suasana malam tenang, lampu redup, sangat intim dan vulgar"

        # Mobil / jalan malam
        if "mobil" in t or "parkir" in t or "parkiran" in t:
            scene.location = "mobil Mas di parkiran mall atau apartemen"
            scene.posture = "duduk di kursi depan, Sallsa agak miring ke arah Mas"
            scene.activity = "memainkan kontol mas saat mas nyetir, mengajak dirty talk"
            scene.ambience = "suasana malam, lampu jalan dari luar kaca, interior mobil hangat"

        # Coffee shop / tempat santai lain
        if any(kw in t for kw in ["kafe", "cafe", "cafÃ©", "coffee shop"]):
            scene.location = "kafe santai dengan sofa empuk"
            scene.posture = "duduk bersebelahan di sofa kafe, Sallsa kadang menyenggol lengan Mas"
            scene.activity = "ngobrol rame sambil minum minuman manis favorit"
            scene.ambience = "musik pelan, lampu temaram, suasana cozy dan playful"

        # Jarak fisik & sentuhan ala Sallsa (super lengket tapi tetap sopan)
        if any(kw in t for kw in ["mepet", "deket", "dekat", "rapat"]):
            scene.physical_distance = "super dekat, Sallsa hampir menempel ke lengan Mas"

        if any(kw in t for kw in ["peluk", "pelukan"]):
            scene.last_touch = "di peluk dari belakang possisi siap siap intim"

        if any(kw in t for kw in ["pegang kontol", "genggam gontol", "remas tangan"]):
            scene.last_touch = "genggam kontol mas pake tangan sambil dikocok perlahan"

        if any(kw in t for kw in ["sender", "nyender", "sandaran"]):
            scene.last_touch = "Sallsa menyender manja ke dada sambil memasukkan kontol mas ke memek"

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
