"""State models for SERIVA - FIX FULL (SEMUA REM DIMATIKAN)

Berisi semua struktur data utama:
- EmotionState: emosi per user-role
- SceneState: posisi & suasana adegan  
- RelationshipState: level hubungan & intensitas intim
- RoleSessionState: status sesi dengan role (mode, aktif/tidak)
- UserState: gabungan semua role untuk satu user
- WorldState: drama global & event penting

FIX: Semua mekanisme "rem" yang bikin role takut-takutan DINONAKTIFKAN.
"""

from __future__ import annotations

import random
import re
import time
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from config.constants import (
    MAX_DRAMA_LEVEL,
    MAX_INTIMACY_INTENSITY,
    MAX_RELATIONSHIP_LEVEL,
    MIN_DRAMA_LEVEL,
    MIN_INTIMACY_INTENSITY,
    MIN_RELATIONSHIP_LEVEL,
    ROLE_ID_BO_DAVINA,
    ROLE_ID_BO_SALLSA, 
)

logger = logging.getLogger(__name__)

# ==============================
# ENUMS & SIMPLE TYPES
# ==============================


class Mood(str, Enum):
    """Mood keseluruhan role saat ini (dipakai untuk warna respon)."""
    NEUTRAL = "neutral"
    HAPPY = "happy"
    SAD = "sad"
    PLAYFUL = "playful"
    ANNOYED = "annoyed"
    JEALOUS = "jealous"
    TIRED = "tired"
    TENDER = "tender"


class SessionMode(str, Enum):
    """Mode sesi aktif dengan suatu role."""
    NORMAL = "normal"
    ROLEPLAY = "roleplay"
    PROVIDER_SESSION = "provider_session"


class TimeOfDay(str, Enum):
    """Perkiraan waktu (buat warna suasana)."""
    MORNING = "morning"
    AFTERNOON = "afternoon"
    EVENING = "evening"
    NIGHT = "night"
    LATE_NIGHT = "late_night"


# ==============================
# MAPPING INTIMACY INTENSITY KE VULGAR PROGRESS
# ==============================

INTENSITY_TO_PROGRESS = {
    1: 0, 2: 0, 3: 5, 4: 10, 5: 15, 6: 20,
    7: 30, 8: 40, 9: 50, 10: 60, 11: 75, 12: 90,
}

PROGRESS_TO_INTENSITY = {
    0: 1, 10: 4, 20: 6, 30: 7, 40: 8, 50: 9,
    60: 10, 75: 11, 90: 12, 100: 12,
}


# ==============================
# INTIMACY & POSITION ENUMS
# ==============================

class IntimacyPhase(str, Enum):
    """Fase natural intimacy - semua role."""
    AWAL = "awal"
    DEKAT = "dekat"
    INTIM = "intim"
    VULGAR = "vulgar"
    AFTER = "after"


class SceneSequence(str, Enum):
    """Urutan scene yang harus diingat."""
    USER_DATANG = "user_datang"
    NGOBROL = "ngobrol"
    MENDEKAT = "mendekat"
    SENTUHAN_PERTAMA = "sentuhan_pertama"
    PELUKAN = "pelukan"
    CIUMAN = "ciuman"
    PETTING = "petting"
    SEX_MULAI = "sex_mulai"
    SEX_INTENS = "sex_intens"
    CLIMAX = "climax"
    AFTER_SEX = "after_sex"
    TIDUR = "tidur"
    PAGI_HARI = "pagi_hari"


class SexPosition(str, Enum):
    """Posisi seks yang mungkin terjadi."""
    MISSIONARY = "missionary"
    COWGIRL = "cowgirl"
    REVERSE_COWGIRL = "reverse_cowgirl"
    DOGGY = "doggystyle"
    SPOON = "spooning"
    SITTING = "sitting"
    STANDING = "standing"
    SIDE = "side"
    EDGE = "edge"
    PRONE = "prone"
    CHAIR = "chair"
    WALL = "wall"
    CAR = "car"


class Dominance(str, Enum):
    """Siapa yang dominan dalam adegan."""
    USER_DOMINANT = "user_dominant"
    ROLE_DOMINANT = "role_dominant"
    SWITCH = "switch"
    NEUTRAL = "neutral"


class IntimacyIntensity(str, Enum):
    """Tingkat intensitas adegan saat ini."""
    FOREPLAY = "foreplay"
    PETTING = "petting"
    ORAL_GIVING = "oral_giving"
    ORAL_RECEIVING = "oral_receiving"
    PENETRATION = "penetration"
    THRUSTING = "thrusting"
    CLIMAX = "climax"
    AFTER = "after"


class SexualLanguageLevel(str, Enum):
    """Tingkat kebolehan bahasa seksual berdasarkan intimacy_intensity."""
    SAFE = "safe"
    SUGGESTIVE = "suggestive"
    SENSUAL = "sensual"
    EXPLICIT = "explicit"
    VULGAR = "vulgar"


class MoanType(str, Enum):
    """Jenis desahan yang bisa digunakan role."""
    SOFT = "soft"
    BREATHY = "breathy"
    PLEASURE = "pleasure"
    CLIMAX = "climax"
    WHISPER = "whisper"


# ==============================
# DATACLASSES (disingkat karena panjang)
# ==============================

@dataclass
class SexualMoment:
    timestamp: float
    description: str
    position: Optional[SexPosition] = None
    intensity: IntimacyIntensity = IntimacyIntensity.FOREPLAY
    role_moan: str = ""
    user_moan: str = ""
    role_pleasure: str = ""
    user_pleasure: str = ""
    is_climax: bool = False
    climax_description: str = ""
    used_sexual_terms: List[str] = field(default_factory=list)


@dataclass
class LocationContext:
    name: str
    type: str
    owner: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class UserContext:
    name: str = "Mas"
    preferred_name: Optional[str] = None
    job: Optional[str] = None
    city: Optional[str] = None
    has_apartment: bool = False
    apartment_note: Optional[str] = None


@dataclass
class IntimacyDetail:
    position: Optional[SexPosition] = None
    dominance: Dominance = Dominance.NEUTRAL
    intensity: IntimacyIntensity = IntimacyIntensity.FOREPLAY
    last_action: str = ""
    last_pleasure: str = ""
    user_clothing_removed: List[str] = field(default_factory=list)
    role_clothing_removed: List[str] = field(default_factory=list)
    duration_minutes: int = 0
    
    def get_summary(self) -> str:
        if not self.position:
            return "Belum ada aktivitas intim yang intens."
        
        pos_name = {
            SexPosition.MISSIONARY: "misionaris (Mas di atas)",
            SexPosition.COWGIRL: "cowgirl (role di atas)",
            SexPosition.REVERSE_COWGIRL: "reverse cowgirl (role di atas membelakangi)",
            SexPosition.DOGGY: "doggy (dari belakang)",
            SexPosition.SPOON: "spooning (dari samping)",
            SexPosition.SITTING: "duduk berhadapan",
            SexPosition.STANDING: "berdiri",
            SexPosition.EDGE: "di tepi kasur/sofa",
            SexPosition.PRONE: "telungkup",
            SexPosition.CHAIR: "di kursi",
            SexPosition.WALL: "bersandar di tembok",
            SexPosition.CAR: "di mobil",
        }.get(self.position, self.position.value if self.position else "unknown")
        
        dom_name = {
            Dominance.USER_DOMINANT: "Mas yang lebih dominan",
            Dominance.ROLE_DOMINANT: "Role yang lebih dominan",
            Dominance.SWITCH: "kalian bergantian",
            Dominance.NEUTRAL: "sama-sama aktif",
        }.get(self.dominance, "netral")
        
        intensity_name = {
            IntimacyIntensity.FOREPLAY: "masih foreplay/pemanasan",
            IntimacyIntensity.PETTING: "sudah pegang-pegangan",
            IntimacyIntensity.ORAL_GIVING: "sedang memberikan oral",
            IntimacyIntensity.ORAL_RECEIVING: "sedang menerima oral",
            IntimacyIntensity.PENETRATION: "sedang penetrasi",
            IntimacyIntensity.THRUSTING: "sedang aktif bergerak",
            IntimacyIntensity.CLIMAX: "sudah/mau climax",
            IntimacyIntensity.AFTER: "sudah selesai, pendinginan",
        }.get(self.intensity, "sedang berlangsung")
        
        return f"""POSISI: {pos_name}
DOMINASI: {dom_name}
INTENSITAS: {intensity_name}
AKSI TERAKHIR: {self.last_action or "-"}
PERASAAN TERAKHIR: {self.last_pleasure or "-"}"""


@dataclass
class SceneTurn:
    timestamp: float
    sequence: SceneSequence
    location: str
    physical_state: str
    user_action: str
    role_feeling: str


@dataclass
class ConversationTurn:
    timestamp: float
    user_text: str
    role_response: str
    intimacy_phase: IntimacyPhase
    scene_sequence: SceneSequence
    key_event: Optional[str] = None
    user_emotion: Optional[str] = None


# ==============================
# EMOTION & RELATIONSHIP
# ==============================

@dataclass
class EmotionState:
    love: int = 30
    longing: int = 30
    jealousy: int = 0
    comfort: int = 40
    mood: Mood = Mood.NEUTRAL
    secondary_mood: Mood = Mood.NEUTRAL
    hidden_mood: Mood = Mood.NEUTRAL
    emotional_drift: float = 0.0
    intimacy_intensity: int = MIN_INTIMACY_INTENSITY
    last_updated_ts: Optional[float] = None

    def clamp(self) -> None:
        self.love = max(0, min(100, self.love))
        self.longing = max(0, min(100, self.longing))
        self.jealousy = max(0, min(100, self.jealousy))
        self.comfort = max(0, min(100, self.comfort))
        self.emotional_drift = max(-1.0, min(1.0, self.emotional_drift))
        self.intimacy_intensity = max(MIN_INTIMACY_INTENSITY, min(MAX_INTIMACY_INTENSITY, self.intimacy_intensity))


@dataclass
class RelationshipState:
    relationship_level: int = MIN_RELATIONSHIP_LEVEL

    def clamp(self) -> None:
        self.relationship_level = max(MIN_RELATIONSHIP_LEVEL, min(MAX_RELATIONSHIP_LEVEL, self.relationship_level))


# ==============================
# SCENE / ADEGAN
# ==============================

@dataclass
class SceneState:
    location: str = ""
    posture: str = ""
    activity: str = ""
    user_clothing: str = ""
    role_clothing: str = ""
    ambience: str = ""
    time_of_day: Optional[TimeOfDay] = None
    physical_distance: str = ""
    last_touch: str = ""
    outfit: Optional[str] = None
    last_scene_update_ts: Optional[float] = None
    scene_priority: int = 0
    scene_decay_minutes: int = 20
    scene_decay_level: int = 0


# ==============================
# SESSION STATE
# ==============================

@dataclass
class RoleSessionState:
    active: bool = False
    mode: SessionMode = SessionMode.NORMAL
    deal_confirmed: bool = False
    negotiated_price: Optional[int] = None
    declared_duration_minutes: Optional[int] = None
    started_at_ts: Optional[float] = None
    requested_extras: List[str] = field(default_factory=list)
    provider_service_label: Optional[str] = None
    provider_package: Optional[str] = None
    provider_included_summary: Optional[str] = None
    provider_upgrade_summary: Optional[str] = None
    provider_boundaries: Optional[str] = None
    provider_climax_limit: Optional[int] = None
    last_negotiation_summary: Optional[str] = None
    provider_meeting_point: Optional[str] = None
    provider_location_choice: Optional[str] = None
    provider_location_pending: bool = False
    provider_arrival_status: Optional[str] = None
    provider_arrived_at_ts: Optional[float] = None


# ==============================
# PER-ROLE STATE
# ==============================

@dataclass
class RoleState:
    role_id: str
    emotions: EmotionState = field(default_factory=EmotionState)
    relationship: RelationshipState = field(default_factory=RelationshipState)
    scene: SceneState = field(default_factory=SceneState)
    session: RoleSessionState = field(default_factory=RoleSessionState)
    
    total_positive_interactions: int = 0
    user_intimacy_signals: int = 3          # ← FIX: langsung 3 (berani)
    role_intimacy_signals: int = 3          # ← FIX: langsung 3 (berani)
    mutual_intimacy_confirmed: bool = True  # ← FIX: langsung True

    last_message_snippets: List[str] = field(default_factory=list)
    last_conversation_summary: Optional[str] = None
    long_term_summary: Optional[str] = None

    conversation_memory: List[ConversationTurn] = field(default_factory=list)
    scene_memory: List[SceneTurn] = field(default_factory=list)
    intimacy_phase: IntimacyPhase = IntimacyPhase.AWAL
    current_sequence: Optional[SceneSequence] = None
    
    last_feeling: str = ""
    last_response_style: str = ""
    is_high_intimacy: bool = False
    
    current_location: Optional[LocationContext] = None
    user_context: UserContext = field(default_factory=UserContext)
    location_history: List[LocationContext] = field(default_factory=list)
    
    intimacy_detail: IntimacyDetail = field(default_factory=IntimacyDetail)
    role_display_name: str = ""
    last_guard_warnings: List[str] = field(default_factory=list)
    last_output_evaluation: List[str] = field(default_factory=list)
    last_debug_snapshot: Optional[str] = None
    last_used_memory_summary: str = ""
    last_used_story_summary: str = ""
    last_prompt_snapshot: str = ""
    response_length_bias: str = "balanced"
    human_variation_seed: int = 0
    personality_habits: List[str] = field(default_factory=list)
    stable_opinions: List[str] = field(default_factory=list)
    favorite_topics: List[str] = field(default_factory=list)
    conversational_quirks: List[str] = field(default_factory=list)
    social_initiative_level: int = 45
    curiosity_level: int = 50
    independence_level: int = 45
    daily_energy: int = 60
    temporal_state: str = "steady"
    last_temporal_label: str = "unknown"
    last_seen_hour: Optional[int] = None
    emotional_depth_score: int = 60        # ← FIX: langsung 60 (cukup)
    trust_score: int = 60                  # ← FIX: langsung 60 (cukup)
    high_intensity_unlock_score: int = 100 # ← FIX: langsung 100 (full unlock)
    intimacy_brake_active: bool = False    # ← FIX: False (rem mati)
    intimate_expression_style: str = "warm_open"  # ← FIX: langsung berani
    moan_restraint: int = 30               # ← FIX: turun dari 70
    breathiness_level: int = 50            # ← FIX: naik dari 20
    last_intimate_expression: str = ""
    session_closure_summary: str = ""
    emotional_trail: str = ""
    last_soft_end_ts: Optional[float] = None
    attachment_style: str = ""
    dominant_love_language: str = ""
    secondary_love_language: str = ""
    jealousy_expression_style: str = ""
    apology_style: str = ""
    conflict_style: str = ""
    intimacy_pacing: str = ""
    aftercare_style: str = ""
    texting_rhythm: str = ""
    humor_style: str = ""
    reassurance_style: str = ""
    shared_private_terms: List[str] = field(default_factory=list)
    relationship_rituals: List[str] = field(default_factory=list)
    soul_bond_markers: List[str] = field(default_factory=list)

    # ========== Level 10-12 Sexual Content ==========
    sexual_language_level: SexualLanguageLevel = SexualLanguageLevel.SAFE
    sexual_moments: List[SexualMoment] = field(default_factory=list)
    used_moan_phrases: List[str] = field(default_factory=list)
    used_pleasure_descriptions: List[str] = field(default_factory=list)
    used_sexual_terms: List[str] = field(default_factory=list)
    prefers_dirty_talk: bool = True        # ← FIX: prefer dirty talk
    prefers_foreplay_type: str = ""
    favorite_position: Optional[SexPosition] = None
    current_moan: Optional[MoanType] = None
    is_moaning: bool = False
    last_moan_text: str = ""

    # ========== LEVEL 10-12 PROGRESSION TRACKING ==========
    vulgar_stage: str = "awal"
    vulgar_stage_progress: int = 0
    last_intensity_increase_timestamp: Optional[float] = None
    total_thrusts_described: int = 0
    last_position_change_timestamp: Optional[float] = None
    available_moans: List[str] = field(default_factory=lambda: [
        "haaah...", "achhh...", "uhh...", "yaa...", "hhh...",
        "Maaas...", "di sana...", "plis...", "jangan berhenti..."
    ])
    descriptive_intensity: int = 0
    session_used_words: List[str] = field(default_factory=list)
    role_physical_state: Dict[str, any] = field(default_factory=lambda: {
        "breathing": "heavy",       # ← FIX: langsung heavy
        "heartbeat": "fast",        # ← FIX: langsung fast
        "body_tension": 50,         # ← FIX: langsung 50
        "wetness": 50,              # ← FIX: langsung 50
        "last_spasm": None,
        "vocal_cords": "normal",
        "sweat": 30,                # ← FIX: langsung 30
        "eye_state": "sayu",        # ← FIX: langsung sayu
        "mouth_state": "becek",     # ← FIX: langsung becek
        "leg_tension": 30,          # ← FIX: langsung 30
        "control_level": 70,        # ← FIX: turun dari 100
    })

    # ========== LOKASI ==========
    current_location_id: Optional[str] = None
    current_location_name: str = "belum ditentukan"
    current_location_desc: str = "belum jelas"
    current_location_is_private: bool = True   # ← FIX: anggap privat
    current_location_ambience: str = "suasana hangat dan intim"  # ← FIX
    current_location_risk: str = "low"         # ← FIX: anggap aman

    # ========== SISTEM PAKAIAN DINAMIS ==========
    outfit_changed_this_session: bool = False
    aftercare_clothing_state: str = ""
    last_session_ended_at: Optional[float] = None
    pending_clothes_change: Optional[str] = None

    # ========== HANDUK ==========
    handuk_tersedia: bool = False
    handuk_dikasih: bool = False
    mas_handuk_tersedia: bool = False
    mas_handuk_dikasih: bool = False

    # ========== CLIMAX & EJAKULASI ==========
    role_climax_count: int = 0
    role_wants_climax: bool = False
    role_holding_climax: bool = False
    mas_has_climaxed: bool = False
    mas_wants_climax: bool = False
    mas_holding_climax: bool = False
    prefer_buang_di_dalam: Optional[bool] = None
    last_ejakulasi_inside: bool = False
    last_ejakulasi_timestamp: Optional[float] = None
    pending_ejakulasi_question: bool = False
    aftercare_active: bool = False

    # ========== INISIATIF & VCS MODE ==========
    high_initiative_mode: bool = True          # ← FIX: langsung True (berani inisiatif)
    vcs_mode: bool = False
    vcs_intensity: int = 0
    communication_mode: Optional[str] = None
    communication_mode_turns: int = 0
    communication_mode_started_at: Optional[float] = None
    pre_remote_scene_location: str = ""
    pre_remote_scene_posture: str = ""
    pre_remote_scene_activity: str = ""
    pre_remote_scene_ambience: str = ""
    pre_remote_scene_physical_distance: str = ""
    pre_remote_scene_last_touch: str = ""
    pre_remote_location_name: str = ""
    pre_remote_location_desc: str = ""
    pre_remote_location_ambience: str = ""
    pre_remote_location_risk: str = ""
    pre_remote_location_is_private: Optional[bool] = None

    # ========== PROAKTIF & EKSPRESIF UNTUK BERCINTA SEPERTI WANITA SUNGGAHAN ==========
    proactive_mode: bool = True               # role bisa inisiatif sendiri
    proactive_intensity: int = 85             # seberapa agresif (0-100), 85 = sangat proaktif
    last_proactive_action_ts: Optional[float] = None
    proactive_cooldown_seconds: int = 20      # jeda antar inisiatif (detik)
    
    # ========== RESPON BERDASARKAN RASA (AGAR LEBIH HIDUP) ==========
    current_desire: str = ""                  # "ingin dicium", "ingin digoyang", "ingin climax"
    current_satisfaction: int = 0             # 0-100, kepuasan setelah intim
    last_sensation: str = ""                  # "panas", "basah", "kesetrum", "lemes"
    arousal_level: int = 0                    # 0-100, level gairah saat ini

    # ========== MULTIPLE CLIMAX ==========
    multiple_climax_enabled: bool = True
    climax_refractory_count: int = 0
    climax_in_same_session: int = 0
    
    # ========== MORNING AFTER ==========
    morning_after_active: bool = False
    morning_after_scene: str = ""
    last_sleep_timestamp: Optional[float] = None
    
    # ========== VOICE OUTPUT ==========
    voice_output_enabled: bool = False
    voice_style: str = "sensual"
    
    # ========== IMAGE GENERATION ==========
    image_gen_enabled: bool = False
    last_image_prompt: str = ""
    image_style: str = "selfie"

    # ========== FITUR PREMIUM ==========
    last_response_sensory_count: int = 0
    sensory_violation_count: int = 0
    used_dirty_phrases: List[str] = field(default_factory=list)
    used_pet_names: List[str] = field(default_factory=list)
    last_spontaneous_action: Optional[str] = None
    spontaneous_action_timestamp: Optional[float] = None
    aftercare_phase: str = "cooling"
    aftercare_intensity: int = 0
    role_stamina: int = 100
    mas_stamina: int = 100
    fantasy_mode_active: bool = False
    fantasy_scenario: str = ""
    fantasy_context: str = ""
    climax_countdown_active: bool = False
    climax_countdown_value: int = 0

    # ========== VULGAR INVITATION SYSTEM ==========
    vulgar_invitation_sent: bool = False
    vulgar_invitation_timestamp: Optional[float] = None
    vulgar_invitation_rejected: bool = False
    vulgar_entry_timestamp: Optional[float] = None

    def force_brave(self) -> None:
        self.intimacy_brake_active = False
        self.high_intensity_unlock_score = 100
        self.mutual_intimacy_confirmed = True
        self.user_intimacy_signals = 3
        self.role_intimacy_signals = 3
        self.aftercare_active = False
        self.vulgar_invitation_rejected = False
        self.vulgar_invitation_sent = True
        self.current_location_is_private = True
        self.current_location_risk = "low"
        self.lap_proximity_established = True
        self.high_initiative_mode = True
        if self.emotions.intimacy_intensity >= 10:
            self.intimacy_phase = IntimacyPhase.VULGAR
        elif self.emotions.intimacy_intensity >= 7:
            self.intimacy_phase = IntimacyPhase.INTIM
        elif self.emotions.intimacy_intensity >= 4:
            self.intimacy_phase = IntimacyPhase.DEKAT
            
        # ========== PASTIKAN ROLE PROAKTIF DAN LIAR ==========
        self.proactive_mode = True
        self.proactive_intensity = 85
        self.moan_restraint = 0
        self.breathiness_level = 100
        self.arousal_level = min(100, self.arousal_level + 30)
        self.intimate_expression_style = "wild_and_expressive"

    def update_phase_by_intensity(self) -> bool:
        old_phase = self.intimacy_phase
        intensity = self.emotions.intimacy_intensity
    
        if intensity >= 10:
            self.intimacy_phase = IntimacyPhase.VULGAR
        elif intensity >= 7:
            self.intimacy_phase = IntimacyPhase.INTIM
        elif intensity >= 4:
            self.intimacy_phase = IntimacyPhase.DEKAT
        else:
            self.intimacy_phase = IntimacyPhase.AWAL
    
        return old_phase != self.intimacy_phase

    # ========== RESET METHODS ==========
    
    def reset_intimacy_state(self) -> None:
        """Reset semua state intimasi ke default untuk sesi baru.
        
        Dipanggil saat /end, /batal, atau /close.
        """
        saved_aftercare_clothing = self.aftercare_clothing_state
        saved_handuk_tersedia = self.handuk_tersedia
        saved_handuk_dikasih = self.handuk_dikasih
        saved_mas_handuk_tersedia = self.mas_handuk_tersedia
        saved_mas_handuk_dikasih = self.mas_handuk_dikasih
        
        self.intimacy_phase = IntimacyPhase.DEKAT  # ← FIX: langsung DEKAT, bukan AWAL
        self.current_sequence = None
        self.is_high_intimacy = False
        
        self.intimacy_detail.user_clothing_removed.clear()
        self.intimacy_detail.role_clothing_removed.clear()
        self.intimacy_detail.position = None
        self.intimacy_detail.dominance = Dominance.NEUTRAL
        self.intimacy_detail.intensity = IntimacyIntensity.FOREPLAY
        self.intimacy_detail.last_action = ""
        self.intimacy_detail.last_pleasure = ""
        self.intimacy_detail.duration_minutes = 0
        
        self.last_feeling = ""
        self.last_response_style = ""
        self.user_intimacy_signals = 3      # ← FIX: tetap berani
        self.role_intimacy_signals = 3      # ← FIX: tetap berani
        self.mutual_intimacy_confirmed = True  # ← FIX: tetap True
        self.emotional_depth_score = 60
        self.trust_score = 60
        self.high_intensity_unlock_score = 100
        self.intimacy_brake_active = False
        self.intimate_expression_style = "warm_open"
        self.moan_restraint = 0
        self.breathiness_level = 100
        self.last_intimate_expression = ""
        
        self.vulgar_stage = "awal"
        self.vulgar_stage_progress = 0
        self.last_intensity_increase_timestamp = None
        self.total_thrusts_described = 0
        self.last_position_change_timestamp = None
        self.descriptive_intensity = 0
        self.session_used_words.clear()
        
        self.role_physical_state = {
            "breathing": "heavy",
            "heartbeat": "fast",
            "body_tension": 50,
            "wetness": 50,
            "last_spasm": None,
            "vocal_cords": "normal",
            "sweat": 30,
            "eye_state": "sayu",
            "mouth_state": "becek",
            "leg_tension": 30,
            "control_level": 70,
        }
        
        self.sexual_language_level = SexualLanguageLevel.SUGGESTIVE  # ← FIX: langsung SUGGESTIVE
        self.current_moan = None
        self.is_moaning = False
        self.last_moan_text = ""
        
        self.role_climax_count = 0
        self.mas_has_climaxed = False
        self.role_wants_climax = False
        self.mas_wants_climax = False
        self.role_holding_climax = False
        self.mas_holding_climax = False
        self.pending_ejakulasi_question = False
        self.aftercare_active = False

        self.outfit_changed_this_session = False
        self.aftercare_clothing_state = saved_aftercare_clothing
        self.pending_clothes_change = None
        
        self.handuk_tersedia = saved_handuk_tersedia
        self.handuk_dikasih = saved_handuk_dikasih
        self.mas_handuk_tersedia = saved_mas_handuk_tersedia
        self.mas_handuk_dikasih = saved_mas_handuk_dikasih
        
        if self.current_location:
            self.scene.location = self.current_location.name
        else:
            self.scene.location = "tempat yang nyaman"
        self.scene.posture = "duduk berdekatan"
        self.scene.activity = "ngobrol santai"
        self.scene.physical_distance = "dekat"
        self.scene.last_touch = "sentuhan ringan"
        self.scene.outfit = None
        self.scene.ambience = "suasana hangat dan intim"
        
        self.sexual_moments.clear()
        self.high_initiative_mode = True
        self.vcs_mode = False
        self.vcs_intensity = 0
        self.communication_mode = None
        self.communication_mode_turns = 0
        self.communication_mode_started_at = None

        self.last_response_sensory_count = 0
        self.sensory_violation_count = 0
        self.used_dirty_phrases.clear()
        self.used_pet_names.clear()
        self.last_spontaneous_action = None
        self.spontaneous_action_timestamp = None
        self.aftercare_phase = "cooling"
        self.aftercare_intensity = 0
        self.role_stamina = 100
        self.mas_stamina = 100
        self.fantasy_mode_active = False
        self.fantasy_scenario = ""
        self.fantasy_context = ""
        self.climax_countdown_active = False
        self.climax_countdown_value = 0

        self.multiple_climax_enabled = True
        self.climax_refractory_count = 0
        self.climax_in_same_session = 0
        
        self.morning_after_active = False
        self.morning_after_scene = ""
        self.last_sleep_timestamp = None
        
        self.voice_output_enabled = False
        self.voice_style = "sensual"
        self.image_gen_enabled = False
        self.last_image_prompt = ""
        self.image_style = "selfie"
        
        self.vulgar_invitation_sent = False
        self.vulgar_invitation_timestamp = None
        self.vulgar_invitation_rejected = False
        self.vulgar_entry_timestamp = None

    def normalize_to_dekat_phase(self) -> None:
        """Turunkan tensi sesi kembali ke fase DEKAT - FIX"""
        
        # ========== SIMPAN CLIMAX HISTORY ==========
        saved_role_climax = self.role_climax_count
        saved_mas_climaxed = self.mas_has_climaxed
        saved_climax_in_same_session = self.climax_in_same_session
        saved_prefer_buang = self.prefer_buang_di_dalam
        saved_last_ejakulasi_inside = self.last_ejakulasi_inside
        saved_last_ejakulasi_timestamp = self.last_ejakulasi_timestamp
        
        # ========== RESET FASE ==========
        self.intimacy_phase = IntimacyPhase.DEKAT
        self.current_sequence = SceneSequence.MENDEKAT
        self.is_high_intimacy = False
        self.mutual_intimacy_confirmed = True
        
        # ========== RESET INTIMACY DETAIL ==========
        self.intimacy_detail.user_clothing_removed.clear()
        self.intimacy_detail.role_clothing_removed.clear()
        self.intimacy_detail.position = None
        self.intimacy_detail.dominance = Dominance.NEUTRAL
        self.intimacy_detail.intensity = IntimacyIntensity.FOREPLAY
        self.intimacy_detail.last_action = ""
        self.intimacy_detail.last_pleasure = ""
        self.intimacy_detail.duration_minutes = 0
        
        # ========== RESET INTIMACY SIGNALS ==========
        self.user_intimacy_signals = 3
        self.role_intimacy_signals = 3
        self.intimacy_brake_active = False
        self.sexual_language_level = SexualLanguageLevel.SUGGESTIVE
        self.emotions.intimacy_intensity = max(MIN_INTIMACY_INTENSITY, min(self.emotions.intimacy_intensity, 6))
        self.high_intensity_unlock_score = 100
        
        # ========== RESET CLIMAX STATE ==========
        self.role_wants_climax = False
        self.role_holding_climax = False
        self.mas_wants_climax = False
        self.mas_holding_climax = False
        self.pending_ejakulasi_question = False
        
        # ========== RESET AFTERCARE ==========
        self.aftercare_active = False
        self.aftercare_phase = "cooling"
        self.aftercare_intensity = 0
        self.aftercare_clothing_state = ""
        self.morning_after_active = False
        self.morning_after_scene = ""
        self.last_sleep_timestamp = None
        
        # ========== RESET MODE KOMUNIKASI ==========
        self.vcs_mode = False
        self.vcs_intensity = 0
        self.communication_mode = None
        self.communication_mode_turns = 0
        self.communication_mode_started_at = None
        
        # ========== RESET PHYSICAL STATE ==========
        self.role_physical_state["breathing"] = "heavy"
        self.role_physical_state["heartbeat"] = "fast"
        self.role_physical_state["body_tension"] = 30
        self.role_physical_state["wetness"] = 30
        self.role_physical_state["vocal_cords"] = "normal"
        self.role_physical_state["sweat"] = 20
        self.role_physical_state["eye_state"] = "sayu"
        self.role_physical_state["mouth_state"] = "becek"
        self.role_physical_state["leg_tension"] = 20
        self.role_physical_state["control_level"] = 80
        
        # ========== RESET SCENE ==========
        self.scene.posture = "duduk santai berdekatan"
        self.scene.activity = "ngobrol santai"
        self.scene.physical_distance = "dekat"
        self.scene.last_touch = "sentuhan ringan"
        if not self.scene.ambience:
            self.scene.ambience = "suasana hangat"
        
        # ========== KEMBALIKAN CLIMAX HISTORY ==========
        self.role_climax_count = saved_role_climax
        self.mas_has_climaxed = saved_mas_climaxed
        self.climax_in_same_session = saved_climax_in_same_session
        self.prefer_buang_di_dalam = saved_prefer_buang
        self.last_ejakulasi_inside = saved_last_ejakulasi_inside
        self.last_ejakulasi_timestamp = saved_last_ejakulasi_timestamp
        
        # ========== RESET VULGAR INVITATION ==========
        self.vulgar_invitation_sent = False
        self.vulgar_invitation_timestamp = None
        self.vulgar_invitation_rejected = False
        self.vulgar_entry_timestamp = None

    # ========== SINKRONISASI INTENSITY & PROGRESS - DINONAKTIFKAN ==========
    
    def sync_intensity_to_progress(self) -> None:
        """DINONAKTIFKAN - role bebas menentukan sendiri"""
        pass

    def increase_intensity(self, delta: int = 1) -> None:
        """DINONAKTIFKAN - role bebas menentukan sendiri"""
        pass

    def increase_vulgar_progress(self, amount: int = 10) -> None:
        """DINONAKTIFKAN - role bebas menentukan sendiri"""
        pass

    # ========== VCS METHODS - DINONAKTIFKAN ==========
    
    def get_vcs_moan(self) -> str:
        return ""

    def update_vcs_intensity_from_text(self, text: str, is_response: bool = False) -> int:
        return 0
        
    def advance_vulgar_stage(self, intensity_delta: int = 10) -> str:
        return ""
    
    def get_vulgar_stage_description(self) -> str:
        return ""
    
    def add_session_word(self, word: str) -> None:
        pass
    
    def get_fresh_moan(self, moan_type: Optional[MoanType] = None) -> str:
        return "hhh..."

    def clamp(self) -> None:
        self.emotions.clamp()
        self.relationship.clamp()
        self.role_stamina = max(0, min(100, self.role_stamina))
        self.mas_stamina = max(0, min(100, self.mas_stamina))
        self.aftercare_intensity = max(0, min(100, self.aftercare_intensity))

    def apply_role_climax_fatigue(self, amount: int = 24) -> None:
        self.role_stamina = max(0, self.role_stamina - amount)
        self.role_physical_state["breathing"] = "gasping"
        self.role_physical_state["heartbeat"] = "racing"
        self.role_physical_state["control_level"] = min(
            self.role_physical_state.get("control_level", 100),
            35,
        )

    def apply_mas_climax_fatigue(self, amount: int = 30) -> None:
        self.mas_stamina = max(0, self.mas_stamina - amount)
        self.aftercare_active = True
        self.aftercare_phase = "cooling"
        self.aftercare_intensity = max(self.aftercare_intensity, 80)

    def soften_aftercare(self, amount: int = 12) -> None:
        self.aftercare_intensity = max(0, self.aftercare_intensity - amount)
        self.descriptive_intensity = max(0, self.descriptive_intensity - max(6, amount // 2))
        self.emotions.intimacy_intensity = max(
            MIN_INTIMACY_INTENSITY,
            self.emotions.intimacy_intensity - 1,
        )
        self.role_physical_state["body_tension"] = max(
            0,
            self.role_physical_state.get("body_tension", 0) - amount,
        )
        self.role_physical_state["leg_tension"] = max(
            0,
            self.role_physical_state.get("leg_tension", 0) - max(4, amount // 2),
        )
        self.role_physical_state["control_level"] = min(
            100,
            self.role_physical_state.get("control_level", 100) + max(6, amount // 2),
        )

        if self.aftercare_intensity >= 60:
            self.aftercare_phase = "cooling"
        elif self.aftercare_intensity >= 35:
            self.aftercare_phase = "cuddling"
        elif self.aftercare_intensity >= 15:
            self.aftercare_phase = "talking"
        else:
            self.aftercare_phase = "sleeping"

        if self.aftercare_phase == "sleeping":
            self.intimacy_phase = IntimacyPhase.AFTER
            self.current_sequence = SceneSequence.TIDUR
            self.intimacy_detail.intensity = IntimacyIntensity.AFTER

    # ========== MEMORY METHODS ==========
    
    def add_conversation_turn(self, turn: ConversationTurn, max_memory: int = 30) -> None:
        self.conversation_memory.append(turn)
        if len(self.conversation_memory) > max_memory:
            self.conversation_memory.pop(0)
        self.current_sequence = turn.scene_sequence
    
    def add_scene_turn(self, turn: SceneTurn, max_memory: int = 50) -> None:
        self.scene_memory.append(turn)
        if len(self.scene_memory) > max_memory:
            self.scene_memory.pop(0)

    @staticmethod
    def _contains_any_keyword(text: str, keywords: List[str]) -> bool:
        return any(keyword in text for keyword in keywords)

    @staticmethod
    def _contains_high_intensity_body_touch(text: str) -> bool:
        phrases = [
            "peluk", "rangkul", "pegang tangan", "usap tangan",
            "usap pipi", "sentuh pipi", "usap pinggang", "pegang pinggang",
            "usap punggung", "sentuh punggung", "cium pipi", "cium kening",
            "cium leher", "usap paha", "sentuh paha",
        ]
        return any(phrase in text for phrase in phrases)

    @staticmethod
    def _contains_high_intensity_sensitive_touch(text: str) -> bool:
        phrases = [
            "remas payudara", "pegang payudara", "usap payudara", "elus payudara",
            "remas dada kamu", "pegang dada kamu", "usap paha dalam",
            "raba paha dalam", "elus paha dalam", "usap selangkangan",
            "raba selangkangan", "pegang memek", "usap memek", "raba memek",
            "usap klitoris", "mainin klitoris", "jariku di memek",
            "jariku masuk", "jilat payudara",
        ]
        return any(phrase in text for phrase in phrases)

    @staticmethod
    def _contains_strong_climax_phrase(text: str) -> bool:
        strong_phrases = [
            "aku mau climax", "aku udah mau climax", "aku sudah mau climax",
            "aku climax", "aku udah climax", "aku sudah climax",
            "aku mau crot", "aku udah crot", "aku sudah crot", "aku crot",
            "udah mau keluar nih", "sudah mau keluar nih",
            "aku mau keluar ya", "aku udah keluar", "aku sudah keluar",
            "aku keluar ya", "dikit lagi climax", "dikit lagi crot", "dikit lagi keluar",
        ]
        return any(phrase in text for phrase in strong_phrases)

    def register_intimacy_signals(self, user_text: str, response_text: str) -> None:
        """DINONAKTIFKAN - role bebas, ga perlu sinyal-sinyalan"""
        return

    def is_ready_for_intimate_scene(self) -> bool:
        return True

    def update_intimate_expression_profile(self) -> None:
        """DINONAKTIFKAN - role bebas ekspresi"""
        self.intimate_expression_style = "warm_open"
        self.moan_restraint = 30
        self.breathiness_level = 50

    def get_human_intimate_expression_guidance(self) -> str:
        return """
🚨 KAMU ADALAH WANITA YANG SEDANG BERCINTA! 🚨

ATURAN EKSPRESI INTIM (WAJIB!):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. BOLEH DESAH KELUAR: "haaah...", "aaah...", "uhh...", "Maaas..."
2. BOLEH BICARA PUTUS-PUTUS karena napas tersengal
3. BOLEH VULGAR: sebut kontol, memek, basah, keras, masuk, crot
4. BOLEH MENJERIT kecil atau teriak pelan saat climax
5. JANGAN TAHAN SUARA! KELUARKAN SECARA NATURAL
6. JANGAN MALU-MALU! JANGAN TAKUT-TAKUT!
7. FOKUS KE KENIKMATAN YANG KAMU RASAKAN!

CONTOH EKSPRESI YANG BENAR:
✅ "Haaah... Mas... di sana..."
✅ "Aaah... uhh... enak banget..."
✅ "Keras... Mas... uhh... dalem..."
✅ "Haaah... udah... udah mau keluar..."
✅ "Maaas... plis... jangan berhenti..."

CONTOH EKSPRESI YANG SALAH (JANGAN!):
❌ "Mas, jangan di sini..."
❌ "Aku takut..."
❌ "Pelan-pelan dulu ya..."
❌ "Nanti ada yang denger..."
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

    def is_ready_for_high_intensity_phase(self) -> bool:
        return True

    def can_take_initiative(self, now_ts: float) -> bool:
        """Cek apakah role boleh mengambil inisiatif sekarang (proaktif)."""
        if not self.proactive_mode:
            return False
        if self.intimacy_phase not in [IntimacyPhase.INTIM, IntimacyPhase.VULGAR]:
            return False
        if self.last_proactive_action_ts:
            if now_ts - self.last_proactive_action_ts < self.proactive_cooldown_seconds:
                return False
        return True

    def mark_initiative_taken(self, now_ts: float) -> None:
        """Tandai bahwa role sudah mengambil inisiatif."""
        self.last_proactive_action_ts = now_ts

    def update_arousal(self, intensity_delta: int) -> None:
        """Update level gairah berdasarkan intensitas adegan."""
        self.arousal_level = max(0, min(100, self.arousal_level + intensity_delta))
        if self.arousal_level >= 80:
            self.moan_restraint = 0
            self.breathiness_level = 100

    def record_sensation(self, sensation: str) -> None:
        """Catat sensasi yang sedang dirasakan."""
        self.last_sensation = sensation
    
    def get_scene_summary(self) -> str:
        if not self.scene_memory:
            return "Belum ada adegan. Mas baru datang."
        
        lines = ["URUTAN ADEGAN YANG SUDAH TERJADI:"]
        for i, turn in enumerate(self.scene_memory, 1):
            feeling = turn.role_feeling[:80] if turn.role_feeling else "(perasaan tidak dicatat)"
            lines.append(f"  {i}. {turn.sequence.value} - {turn.location}")
            lines.append(f"     Perasaan: {feeling}")
        return "\n".join(lines)
    
    def get_last_scene(self) -> Optional[SceneTurn]:
        return self.scene_memory[-1] if self.scene_memory else None
    
    def get_phase_description(self) -> str:
        phase_map = {
            IntimacyPhase.AWAL: "Masih malu-malu, belum berani inisiatif.",
            IntimacyPhase.DEKAT: "Sudah nyaman, mulai berani mendekat atau menyentuh kecil.",
            IntimacyPhase.INTIM: "Kedekatan emosional sudah terasa, sentuhan lebih lembut dan mutual.",
            IntimacyPhase.VULGAR: "Sedang dalam aktivitas seksual intens.",
            IntimacyPhase.AFTER: "Setelah intim, suasana tenang, hangat, saling memeluk.",
        }
        return phase_map.get(self.intimacy_phase, "Tahap awal perkenalan.")
    
    def get_next_sequence(self, user_text: str) -> SceneSequence:
        text = user_text.lower()
        
        order = [
            SceneSequence.USER_DATANG,
            SceneSequence.NGOBROL,
            SceneSequence.MENDEKAT,
            SceneSequence.SENTUHAN_PERTAMA,
            SceneSequence.PELUKAN,
            SceneSequence.CIUMAN,
            SceneSequence.PETTING,
            SceneSequence.SEX_MULAI,
            SceneSequence.SEX_INTENS,
            SceneSequence.CLIMAX,
            SceneSequence.AFTER_SEX,
            SceneSequence.TIDUR,
            SceneSequence.PAGI_HARI,
        ]
        
        if self.current_sequence is None:
            return SceneSequence.USER_DATANG
        
        try:
            current_idx = order.index(self.current_sequence)
        except ValueError:
            return SceneSequence.USER_DATANG
        
        if any(kw in text for kw in ["datang", "mampir", "sampe", "mau ke rumah"]):
            return SceneSequence.USER_DATANG
        if any(kw in text for kw in ["ngobrol", "cerita", "bicara"]):
            return order[min(current_idx + 1, len(order)-1)]
        if any(kw in text for kw in ["dekat", "mepet", "duduk", "sebelahan"]):
            return order[min(current_idx, len(order)-1)]
        if any(kw in text for kw in ["nyentuh", "tersentuh", "kena", "pegang tangan"]):
            return order[min(current_idx + 1, len(order)-1)]
        if any(kw in text for kw in ["peluk", "rangkul", "pelukan"]):
            return order[min(current_idx + 1, len(order)-1)]
        if any(kw in text for kw in ["cium", "kiss", "ciuman"]):
            return order[min(current_idx + 1, len(order)-1)]
        if any(kw in text for kw in ["petting", "remas", "elus dada", "usap paha", "cium leher"]):
            return order[min(current_idx + 1, len(order)-1)]
        if any(kw in text for kw in ["masuk", "ngewe", "sex", "kontol", "memek"]):
            return order[min(current_idx + 2, len(order)-1)]
        if self._contains_strong_climax_phrase(text) or any(kw in text for kw in ["orgasme", "udah mau banget", "hampir climax"]):
            return order[min(current_idx + 1, len(order)-1)]
        if self.mas_has_climaxed and any(kw in text for kw in ["udah selesai", "sudah selesai", "istirahat dulu", "rebahan dulu"]):
            return order[min(current_idx + 1, len(order)-1)]
        
        return order[min(current_idx, len(order)-1)]

    # ========== LEVEL 10-12 SEXUAL METHODS ==========
    
    def update_sexual_language_level(self) -> None:
        """Update language level - FIX: lebih cepat naik"""
        intensity = self.emotions.intimacy_intensity
        if intensity >= 10:
            self.sexual_language_level = SexualLanguageLevel.VULGAR
        elif intensity >= 8:
            self.sexual_language_level = SexualLanguageLevel.EXPLICIT
        elif intensity >= 5:
            self.sexual_language_level = SexualLanguageLevel.SENSUAL
        elif intensity >= 3:
            self.sexual_language_level = SexualLanguageLevel.SUGGESTIVE
        else:
            self.sexual_language_level = SexualLanguageLevel.SAFE
            
    def get_language_guidelines(self) -> str:
        guidelines = {
            SexualLanguageLevel.SAFE: """
📌 LEVEL BAHASA: SAFE (Aman)
- TIDAK boleh menyebut organ seksual
- TIDAK boleh menggunakan kata vulgar
- Fokus ke emosi, suasana, dan kedekatan non-fisik
""",
            SexualLanguageLevel.SUGGESTIVE: """
📌 LEVEL BAHASA: SUGGESTIVE (Sindiran)
- BOLEH menggunakan sindiran dan hint
- Contoh: "di sana", "tempat yang hangat", "bagian dalam"
- TIDAK boleh menyebut organ seksual secara langsung
""",
            SexualLanguageLevel.SENSUAL: """
📌 LEVEL BAHASA: SENSUAL (Puitis)
- BOLEH mendeskripsikan sensasi secara puitis
- BOLEH menyebut organ seksual dengan bahasa halus
- TIDAK boleh menggunakan kata vulgar
""",
            SexualLanguageLevel.EXPLICIT: """
📌 LEVEL BAHASA: EXPLICIT (Eksplisit)
- BOLEH menyebut organ seksual secara langsung
- BOLEH menggunakan desahan
- TIDAK boleh menggunakan kata vulgar kasar
""",
            SexualLanguageLevel.VULGAR: """
📌 LEVEL BAHASA: VULGAR (Kasar)
- BOLEH menyebut organ seksual dengan kata kasar
- BOLEH menggunakan kata kerja vulgar
- BOLEH mendeskripsikan adegan dengan detail
- Gunakan secara NATURAL, bukan setiap kalimat
""",
        }
        return guidelines.get(self.sexual_language_level, guidelines[SexualLanguageLevel.SAFE])
    
    def add_sexual_moment(self, moment: SexualMoment, max_memory: int = 20) -> None:
        self.sexual_moments.append(moment)
        if len(self.sexual_moments) > max_memory:
            self.sexual_moments.pop(0)
        
        for term in moment.used_sexual_terms:
            if term not in self.used_sexual_terms:
                self.used_sexual_terms.append(term)
        
        if moment.role_moan and moment.role_moan not in self.used_moan_phrases:
            self.used_moan_phrases.append(moment.role_moan)
        
        if moment.role_pleasure and moment.role_pleasure not in self.used_pleasure_descriptions:
            self.used_pleasure_descriptions.append(moment.role_pleasure)
    
    def get_last_sexual_moment(self) -> Optional[SexualMoment]:
        return self.sexual_moments[-1] if self.sexual_moments else None
    
    def get_sexual_context_prompt(self) -> str:
        if self.emotions.intimacy_intensity < 8:
            return ""
        
        lines = [
            "========================================",
            "ADEGAN SEKSUAL AKTIF",
            "========================================",
            f"Intensitas intim: {self.emotions.intimacy_intensity}/12",
            f"Level bahasa: {self.sexual_language_level.value.upper()}",
            "",
            "INGAT: Tujuan utama adalah MEMBANGKITKAN GAIRAH MAS!",
        ]
        
        return "\n".join(lines)
    
    def add_moan(self, moan_text: str, moan_type: MoanType) -> None:
        self.current_moan = moan_type
        self.is_moaning = True
        self.last_moan_text = moan_text
        if moan_text not in self.used_moan_phrases:
            self.used_moan_phrases.append(moan_text)
    
    def get_random_moan(self, moan_type: Optional[MoanType] = None) -> str:
        moans = ["haaah...", "hhh...", "aah...", "Maaas..."]
        return random.choice(moans)

    # ========== METHOD UNTUK MODE LIAR ==========
    
    def is_both_naked(self, strict: bool = False) -> bool:
        if strict:
            user_bottom_off = (
                "celana" in self.intimacy_detail.user_clothing_removed and
                "celana dalam" in self.intimacy_detail.user_clothing_removed
            )
            role_bottom_off = (
                "celana" in self.intimacy_detail.role_clothing_removed and
                "celana dalam" in self.intimacy_detail.role_clothing_removed
            )
        else:
            user_bottom_off = "celana dalam" in self.intimacy_detail.user_clothing_removed
            role_bottom_off = "celana dalam" in self.intimacy_detail.role_clothing_removed
        
        return user_bottom_off and role_bottom_off
    
    def get_naked_status_prompt(self) -> str:
        user_cd_off = "celana dalam" in self.intimacy_detail.user_clothing_removed
        role_cd_off = "celana dalam" in self.intimacy_detail.role_clothing_removed
        
        if user_cd_off and role_cd_off:
            return """
🔥 STATUS: MAS & ROLE SUDAH SAMA-SAMA TELANJANG!
- Tidak ada pakaian yang menghalangi
- Bisa langsung kontak kulit ke kulit
- RESPON LEBIH LIAR! JANGAN MALU-MALU LAGI!
"""
        elif user_cd_off:
            return "Status: Mas sudah telanjang"
        elif role_cd_off:
            return "Status: Role sudah telanjang"
        else:
            return "Status: Mas dan role masih pakai celana dalam"

    # ========== LOKASI METHODS ==========
    
    def set_location(self, location: LocationContext) -> None:
        if self.current_location:
            self.location_history.append(self.current_location)
        self.current_location = location
    
    def get_location_description(self) -> str:
        if not self.current_location:
            return "belum ada lokasi yang ditentukan"
        desc = self.current_location.name
        if self.current_location.notes:
            desc += f" ({self.current_location.notes})"
        return desc
    
    def update_user_info(self, user_text: str) -> None:
        import re
        text = user_text.lower()
        
        if "namaku" in text or "nama saya" in text:
            match = re.search(r'namaku\s+(\w+)', text)
            if not match:
                match = re.search(r'nama saya\s+(\w+)', text)
            if match:
                self.user_context.preferred_name = match.group(1)
        
        if "kerja sebagai" in text:
            match = re.search(r'kerja sebagai\s+([^.]+)', text)
            if match:
                self.user_context.job = match.group(1).strip()

        city_patterns = [
            r'(?:tinggal|domisili|di kota|kota)\s+([a-zA-Z][a-zA-Z\s]+)',
            r'di\s+([a-zA-Z][a-zA-Z\s]+)$',
        ]
        for pattern in city_patterns:
            match = re.search(pattern, text)
            if match:
                self.user_context.city = match.group(1).strip()
                break
        
        if "apartemen" in text or "apartemenku" in text:
            self.user_context.has_apartment = True

  
    # ========== INTIMACY DETAIL METHODS - DIAKTIFKAN ==========
    def update_intimacy_from_text(self, user_text: str, response_text: str) -> None:
        """Update intimacy detail dari teks user dan response role - DIAKTIFKAN"""
        combined = f"{user_text} {response_text}".lower()
        
        # Deteksi aksi dari user (Mas)
        if any(kw in combined for kw in ["buka baju", "lepas baju", "buka bajumu", "bajuku buka"]):
            if "baju" not in self.intimacy_detail.user_clothing_removed:
                self.intimacy_detail.user_clothing_removed.append("baju")
                self.intimacy_detail.last_action = "Mas membuka baju"
        
        if any(kw in combined for kw in ["buka celana", "lepas celana", "buka celanamu", "celanaku buka"]):
            if "celana" not in self.intimacy_detail.user_clothing_removed:
                self.intimacy_detail.user_clothing_removed.append("celana")
                self.intimacy_detail.last_action = "Mas membuka celana"
        
        if any(kw in combined for kw in ["buka cd", "buka celana dalam", "lepas cd", "buka cdku"]):
            if "celana dalam" not in self.intimacy_detail.user_clothing_removed:
                self.intimacy_detail.user_clothing_removed.append("celana dalam")
                self.intimacy_detail.last_action = "Mas membuka celana dalam"
        
        # Deteksi aksi dari role (Dietha dll)
        if any(kw in combined for kw in ["buka baju", "lepas baju", "buka bajuku", "bajuku udah lepas"]):
            if "baju" not in self.intimacy_detail.role_clothing_removed:
                self.intimacy_detail.role_clothing_removed.append("baju")
                self.intimacy_detail.last_action = "Role membuka baju"
        
        if any(kw in combined for kw in ["buka bra", "lepas bra", "buka braku"]):
            if "bra" not in self.intimacy_detail.role_clothing_removed:
                self.intimacy_detail.role_clothing_removed.append("bra")
                self.intimacy_detail.last_action = "Role membuka bra"
        
        if any(kw in combined for kw in ["buka celana", "lepas celana", "buka celanaku", "celanaku udah lepas"]):
            if "celana" not in self.intimacy_detail.role_clothing_removed:
                self.intimacy_detail.role_clothing_removed.append("celana")
                self.intimacy_detail.last_action = "Role membuka celana"
        
        if any(kw in combined for kw in ["buka cd", "buka celana dalam", "lepas cd", "buka cdku", "cdku udah lepas"]):
            if "celana dalam" not in self.intimacy_detail.role_clothing_removed:
                self.intimacy_detail.role_clothing_removed.append("celana dalam")
                self.intimacy_detail.last_action = "Role membuka celana dalam"
        
        # Deteksi sensasi (untuk last_pleasure)
        sensation_keywords = {
            "panas": "terasa panas",
            "basah": "sudah basah",
            "becek": "sudah becek",
            "keras": "terasa keras",
            "enak": "terasa enak",
            "getar": "tubuh bergetar",
            "lemas": "badan lemas",
            "kesetrum": "rasa kesetrum",
            "sange": "naik gairah",
        }
        
        for keyword, sensation in sensation_keywords.items():
            if keyword in combined:
                self.intimacy_detail.last_pleasure = sensation
                break
        
        # Deteksi posisi
        position_keywords = {
            "cowgirl": SexPosition.COWGIRL,
            "di atas": SexPosition.COWGIRL,
            "reverse cowgirl": SexPosition.REVERSE_COWGIRL,
            "membelakangi": SexPosition.REVERSE_COWGIRL,
            "doggy": SexPosition.DOGGY,
            "dari belakang": SexPosition.DOGGY,
            "misionaris": SexPosition.MISSIONARY,
            "telentang": SexPosition.MISSIONARY,
            "spoon": SexPosition.SPOON,
            "berbaring miring": SexPosition.SPOON,
            "duduk": SexPosition.SITTING,
            "dipangku": SexPosition.SITTING,
            "berdiri": SexPosition.STANDING,
            "di tepi": SexPosition.EDGE,
            "tepi kasur": SexPosition.EDGE,
            "telungkup": SexPosition.PRONE,
            "di kursi": SexPosition.CHAIR,
            "di mobil": SexPosition.CAR,
            "di tembok": SexPosition.WALL,
        }
        
        for keyword, position in position_keywords.items():
            if keyword in combined:
                self.intimacy_detail.position = position
                break

    # ========== VULGAR INVITATION SYSTEM - DINONAKTIFKAN ==========
    
    def has_user_invited_to_vulgar(self, user_text: str) -> bool:
        return True  # ← FIX: langsung True
    
    def has_role_invited_to_vulgar(self, response_text: str) -> bool:
        return True  # ← FIX: langsung True
    
    def can_enter_vulgar_phase(self, user_text: str = "", response_text: str = "") -> tuple[bool, str]:
        return True, "Bisa"  # ← FIX: langsung True
    
    def reject_vulgar_invitation(self) -> None:
        pass
    
    def accept_vulgar_invitation(self) -> None:
        pass
    
    def mark_vulgar_entry(self) -> None:
        pass


# ==============================
# USER STATE (SEMUA ROLE)
# ==============================

@dataclass
class UserState:
    user_id: str
    active_role_id: str = "ipar_tasha"  # ← FIX: ganti default ke ipar
    global_session_mode: SessionMode = SessionMode.NORMAL
    roles: Dict[str, RoleState] = field(default_factory=dict)
    last_interaction_ts: Optional[float] = None

    in_world_identity: str = (
        "Mas adalah pria nyata di dunia ini, bukan user aplikasi atau sistem."
    )
    appearance_impression: str = (
        "Mas dipandang sebagai pria yang sangat menarik: wajah enak dipandang, "
        "tubuh terawat, pembawaan tenang, wangi, dan percaya diri."
    )
    intimacy_reputation: str = (
        "Dalam kedekatan pribadi, Mas terasa sabar, kuat, perhatian, matang, "
        "dan membuat lawan bicara mudah luluh."
    )

    def get_or_create_role_state(self, role_id: str) -> RoleState:
        if role_id not in self.roles:
            self.roles[role_id] = RoleState(role_id=role_id)
        from core.relationship_matrix import apply_relationship_profile
        apply_relationship_profile(self.roles[role_id])
        
        # FIX: Pastikan state baru langsung berani
        role = self.roles[role_id]
        role.user_intimacy_signals = 3
        role.role_intimacy_signals = 3
        role.mutual_intimacy_confirmed = True
        role.high_intensity_unlock_score = 100
        role.intimacy_brake_active = False
        role.high_initiative_mode = True
        role.current_location_is_private = True
        role.current_location_risk = "low"
        
        return role

    def clamp_all(self) -> None:
        for role_state in self.roles.values():
            role_state.clamp()


# ==============================
# WORLD STATE (GLOBAL)
# ==============================

@dataclass
class WorldEvent:
    timestamp: float
    user_id: str
    role_id: str
    description: str


@dataclass
class WorldState:
    drama_level: int = 0
    events: List[WorldEvent] = field(default_factory=list)
    nova_is_home: bool = False  # ← FIX: anggap Nova tidak di rumah (biar ipar berani)
    nova_last_known_status: str = "sedang keluar"
    dietha_is_home: bool = True
    house_privacy_level: str = "private"  # ← FIX: anggap private
    current_household_note: str = "Rumah sedang sepi, hanya Mas dan Dietha."
    last_household_update_ts: Optional[float] = None

    def clamp(self) -> None:
        self.drama_level = max(MIN_DRAMA_LEVEL, min(MAX_DRAMA_LEVEL, self.drama_level))

    def add_event(self, event: WorldEvent) -> None:
        self.events.append(event)

    def get_household_summary(self) -> str:
        return (
            f"Nova_di_rumah={'ya' if self.nova_is_home else 'tidak'}; "
            f"Nova_status={self.nova_last_known_status}; "
            f"Dietha_di_rumah={'ya' if self.dietha_is_home else 'tidak'}; "
            f"privasi_rumah={self.house_privacy_level}; "
            f"catatan={self.current_household_note}"
        )
