"""State models for SERIVA.

Berisi semua struktur data utama:
- EmotionState: emosi per user-role
- SceneState: posisi & suasana adegan
- RelationshipState: level hubungan & intensitas intim
- RoleSessionState: status sesi dengan role (mode, aktif/tidak)
- UserState: gabungan semua role untuk satu user
- WorldState: drama global & event penting

Semua angka level hanya dipakai untuk logika internal, jangan bocor ke user
secara teknis (di-convert jadi gaya bahasa/gestur oleh role & prompt).
"""

from __future__ import annotations

import random
import time
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
)


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
    TENDER = "tender"  # lembut, sayang


class SessionMode(str, Enum):
    """Mode sesi aktif dengan suatu role."""

    NORMAL = "normal"          # chat biasa
    ROLEPLAY = "roleplay"      # mode roleplay intim
    PROVIDER_SESSION = "provider_session"  # sesi layanan (terapis, teman spesial)


class TimeOfDay(str, Enum):
    """Perkiraan waktu (buat warna suasana)."""

    MORNING = "morning"
    AFTERNOON = "afternoon"
    EVENING = "evening"
    NIGHT = "night"
    LATE_NIGHT = "late_night"


# ==============================
# INTIMACY & POSITION ENUMS
# ==============================

class IntimacyPhase(str, Enum):
    """Fase natural intimacy - semua role."""
    AWAL = "awal"           # masih canggung, jaga jarak
    DEKAT = "dekat"         # mulai nyaman, sentuhan tidak sengaja
    INTIM = "intim"         # pelukan, genggaman, napas dekat
    VULGAR = "vulgar"       # aktivitas seksual intens (level 10-12)
    AFTER = "after"         # setelah intim, suasana tenang/hangat


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


# ==============================
# BARU: LEVEL 10-11-12 (SEXUAL CONTENT)
# ==============================

class SexualLanguageLevel(str, Enum):
    """Tingkat kebolehan bahasa seksual berdasarkan intimacy_intensity."""
    
    SAFE = "safe"               # level 1-3: tidak ada bahasa seksual
    SUGGESTIVE = "suggestive"   # level 4-6: sindiran,暗示
    SENSUAL = "sensual"         # level 7-9: bahasa puitis, tidak eksplisit
    EXPLICIT = "explicit"       # level 10-12: boleh organ seksual, desahan detail


class MoanType(str, Enum):
    """Jenis desahan yang bisa digunakan role."""
    SOFT = "soft"           # desahan pelan: "hhh...", "aaah..."
    BREATHY = "breathy"     # napas berat: "haaah... haaah..."
    PLEASURE = "pleasure"   # desahan nikmat: "aaah... enak Maaas..."
    CLIMAX = "climax"       # desahan klimaks: "HAAAH... UDAH... KELUAR..."
    WHISPER = "whisper"     # bisikan: "psst... di sana..."


@dataclass
class SexualMoment:
    """Momen seksual yang terjadi (disimpan untuk konsistensi cerita)."""
    
    timestamp: float
    description: str                       # deskripsi naratif adegan
    position: Optional[SexPosition] = None
    intensity: IntimacyIntensity = IntimacyIntensity.FOREPLAY
    role_moan: str = ""                    # desahan role
    user_moan: str = ""                    # desahan user kalau ada
    role_pleasure: str = ""                # rasa yang dialami role
    user_pleasure: str = ""                # rasa yang dialami user
    is_climax: bool = False
    climax_description: str = ""           # deskripsi saat klimaks
    used_sexual_terms: List[str] = field(default_factory=list)  # organ seksual yang disebut


# ==============================
# LOCATION & USER CONTEXT
# ==============================


@dataclass
class LocationContext:
    """Informasi lengkap tentang lokasi saat ini."""
    name: str
    type: str  # "private", "public", "semi_public"
    owner: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class UserContext:
    """Informasi tentang user (Mas) yang harus diingat role."""
    name: str = "Mas"
    preferred_name: Optional[str] = None
    job: Optional[str] = None
    city: Optional[str] = None
    has_apartment: bool = False
    apartment_note: Optional[str] = None


@dataclass
class IntimacyDetail:
    """Detail lengkap adegan intim saat ini."""
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
    """Satu adegan yang disimpan."""
    timestamp: float
    sequence: SceneSequence
    location: str
    physical_state: str
    user_action: str
    role_feeling: str


@dataclass
class ConversationTurn:
    """Satu putaran percakapan yang disimpan."""
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
    """Emosi per user-role.

    Semua nilai 0–100, tapi dipakai secara relatif saja.
    """

    love: int = 30            # seberapa sayang
    longing: int = 30         # seberapa kangen
    jealousy: int = 0         # seberapa cemburu
    comfort: int = 40         # seberapa nyaman
    mood: Mood = Mood.NEUTRAL

    # Intensitas intim non-vulgar (1–12, sejalan dengan relationship_level)
    intimacy_intensity: int = MIN_INTIMACY_INTENSITY

    def clamp(self) -> None:
        """Pastikan nilai tetap di dalam rentang yang wajar."""

        self.love = max(0, min(100, self.love))
        self.longing = max(0, min(100, self.longing))
        self.jealousy = max(0, min(100, self.jealousy))
        self.comfort = max(0, min(100, self.comfort))

        self.intimacy_intensity = max(
            MIN_INTIMACY_INTENSITY,
            min(MAX_INTIMACY_INTENSITY, self.intimacy_intensity),
        )


@dataclass
class RelationshipState:
    """Level hubungan per user-role.

    relationship_level: 1–12 (Stranger → Intimate)
    """

    relationship_level: int = MIN_RELATIONSHIP_LEVEL

    def clamp(self) -> None:
        self.relationship_level = max(
            MIN_RELATIONSHIP_LEVEL,
            min(MAX_RELATIONSHIP_LEVEL, self.relationship_level),
        )


# ==============================
# SCENE / ADEGAN
# ==============================


@dataclass
class SceneState:
    """Kondisi adegan terakhir antara user dan role.

    Semua field boleh kosong kalau belum di-set.
    """

    location: str = ""          # contoh: "kamar", "ruang tamu", "kafe", "mobil"
    posture: str = ""           # contoh: "duduk di sofa", "rebahan", "berdiri dekat jendela"
    activity: str = ""          # contoh: "nonton film", "ngobrol", "rebahan bareng"

    user_clothing: str = ""     # optional, pakaian user (kalau mau dipakai halus)
    role_clothing: str = ""     # optional, pakaian role (bisa digabung ke outfit kalau mau)

    ambience: str = ""          # contoh: "lampu redup", "hujan di luar", "musik pelan"
    time_of_day: Optional[TimeOfDay] = None

    physical_distance: str = "" # contoh: "jauh", "sebelahan", "sangat dekat", "pelukan"
    last_touch: str = ""        # contoh: "genggam tangan", "peluk", "elus rambut"

    outfit: Optional[str] = None # ringkasan penampilan role saat ini (opsional)

    last_scene_update_ts: Optional[float] = None


# ==============================
# SESSION STATE (MODE & STATUS)
# ==============================


@dataclass
class RoleSessionState:
    """Status sesi aktif per user-role.

    Penting: sesi TIDAK pernah berakhir otomatis.
    - session_active hanya berubah jadi False kalau user mengirim command END
      (misal /end atau /batal, tergantung implementasi handler).
    """

    active: bool = False
    mode: SessionMode = SessionMode.NORMAL

    # Misalnya buat provider: menyimpan apakah sudah /deal, harga, dsb.
    deal_confirmed: bool = False
    negotiated_price: Optional[int] = None

    # Misalnya untuk sesi panjang (companion 6 jam, pijat), ini hanya info cerita.
    # Sistem TIDAK mengakhiri sesi otomatis walaupun durasi habis.
    declared_duration_minutes: Optional[int] = None

    # Timestamp mulai sesi (opsional, buat worker kalau perlu efek longing/drama).
    started_at_ts: Optional[float] = None

    # Ringkasan dunia provider yang sudah disepakati.
    provider_service_label: Optional[str] = None
    provider_included_summary: Optional[str] = None
    provider_upgrade_summary: Optional[str] = None
    provider_boundaries: Optional[str] = None
    last_negotiation_summary: Optional[str] = None


# ==============================
# PER-ROLE STATE (untuk satu user)
# ==============================


@dataclass
class RoleState:
    """State lengkap untuk satu role terhadap satu user."""

    role_id: str
    emotions: EmotionState = field(default_factory=EmotionState)
    relationship: RelationshipState = field(default_factory=RelationshipState)
    scene: SceneState = field(default_factory=SceneState)
    session: RoleSessionState = field(default_factory=RoleSessionState)
    
    total_positive_interactions: int = 0
    user_intimacy_signals: int = 0
    role_intimacy_signals: int = 0
    mutual_intimacy_confirmed: bool = False

    # Riwayat chat singkat per role (ID pesan atau text pendek, detail di memory/message_history)
    last_message_snippets: List[str] = field(default_factory=list)
    last_conversation_summary: Optional[str] = None
    long_term_summary: Optional[str] = None  # kalau nanti kamu pakai

    # Memory System
    conversation_memory: List[ConversationTurn] = field(default_factory=list)
    scene_memory: List[SceneTurn] = field(default_factory=list)
    intimacy_phase: IntimacyPhase = IntimacyPhase.AWAL
    current_sequence: Optional[SceneSequence] = None
    
    # Hindari repetisi
    last_feeling: str = ""
    last_response_style: str = ""
    is_high_intimacy: bool = False
    
    # Location & User Context
    current_location: Optional[LocationContext] = None
    user_context: UserContext = field(default_factory=UserContext)
    location_history: List[LocationContext] = field(default_factory=list)
    
    # Intimacy Detail
    intimacy_detail: IntimacyDetail = field(default_factory=IntimacyDetail)
    role_display_name: str = ""

    # ========== BARU: Level 10-12 Sexual Content ==========
    sexual_language_level: SexualLanguageLevel = SexualLanguageLevel.SAFE
    sexual_moments: List[SexualMoment] = field(default_factory=list)
    
    # Kata-kata sensual yang sudah pernah dipakai (hindari repetisi)
    used_moan_phrases: List[str] = field(default_factory=list)
    used_pleasure_descriptions: List[str] = field(default_factory=list)
    used_sexual_terms: List[str] = field(default_factory=list)  # organ seksual yang pernah disebut
    
    # Preferensi role dalam adegan seks (belajar dari interaksi)
    prefers_dirty_talk: bool = False      # role suka diajak bicara vulgar?
    prefers_foreplay_type: str = ""       # "kissing", "touching", "oral"
    favorite_position: Optional[SexPosition] = None
    
    # Status seksual saat ini
    current_moan: Optional[MoanType] = None
    is_moaning: bool = False
    last_moan_text: str = ""

    # ========== BARU: LEVEL 10-12 PROGRESSION TRACKING ==========
    
    # Tahapan dalam fase VULGAR (lebih granular)
    vulgar_stage: str = "awal"  # "awal", "memanas", "panas", "puncak", "after"
    vulgar_stage_progress: int = 0  # 0-100, progres dalam stage saat ini
    
    # Statistik untuk membuat respons lebih hidup
    last_intensity_increase_timestamp: Optional[float] = None
    total_thrusts_described: int = 0  # sudah berapa kali deskripsi gerakan
    last_position_change_timestamp: Optional[float] = None
    
    # Variasi desahan (biar gak repetitif)
    available_moans: List[str] = field(default_factory=lambda: [
        "haaah...", "achhh...", "uhh...", "yaa...", "hhh...",
        "Maaas...", "di sana...", "plis...", "jangan berhenti..."
    ])
    
    # Intensitas deskripsi (semakin tinggi, semakin detail)
    descriptive_intensity: int = 0  # 0-100, naik seiring arousal
    
    # Kata-kata sensual yang sudah dipakai (per session, bukan permanent)
    session_used_words: List[str] = field(default_factory=list)
    
    # Status fisik role yang lebih hidup
    role_physical_state: Dict[str, any] = field(default_factory=lambda: {
        "breathing": "normal",  # normal, heavy, ragged, gasping
        "heartbeat": "normal",  # normal, fast, racing, pounding
        "body_tension": 0,      # 0-100, ketegangan tubuh
        "wetness": 0,           # 0-100, untuk role wanita
        "last_spasm": None,     # timestamp spasme terakhir
        "vocal_cords": "normal",  # normal, strained, breaking
        "sweat": 0,
        "eye_state": "normal",
        "mouth_state": "normal",
        "leg_tension": 0,
        "control_level": 100,
    })

    # ========== LOKASI ==========
    current_location_id: str = "ruang_tamu"
    current_location_name: str = "Ruang Tamu"
    current_location_desc: str = "Ruang tamu dengan sofa nyaman, TV menyala pelan"
    current_location_is_private: bool = False
    current_location_ambience: str = "suasana hangat, lampu tidak terlalu terang"
    current_location_risk: str = "medium"  # low, medium, high

    # ========== HANDUK ==========
    handuk_tersedia: bool = False
    handuk_dikasih: bool = False

    # ========== CLIMAX & EJAKULASI ==========
    # Role climax (role bisa climax berkali-kali)
    role_climax_count: int = 0           # berapa kali role sudah climax
    role_wants_climax: bool = False      # role sedang mau climax
    role_holding_climax: bool = False    # role sedang menahan climax (pending)
    
    # Mas climax (hanya sekali, setelah itu pindah fase AFTER)
    mas_has_climaxed: bool = False       # apakah Mas sudah climax
    mas_wants_climax: bool = False       # Mas sedang mau climax
    mas_holding_climax: bool = False     # Mas menahan climax (tunggu role)
    
    # Preferensi buang (diingat untuk sesi berikutnya)
    prefer_buang_di_dalam: Optional[bool] = None  # True = di dalam, False = di luar
    
    # Status ejakulasi terakhir
    last_ejakulasi_inside: bool = False   # True = di dalam, False = di luar
    last_ejakulasi_timestamp: Optional[float] = None
    
    # Pending decision (role nanya dulu sebelum Mas climax)
    pending_ejakulasi_question: bool = False  # role sudah nanya "buang di dalam/luar?"
    aftercare_active: bool = False

    # ========== RESET METHODS ==========
    
    def reset_intimacy_state(self) -> None:
        """Reset semua state intimasi ke default untuk sesi baru.
        
        Dipanggil saat /end, /batal, atau /close.
        Mempertahankan: relationship_level, emotions (love/longing/comfort),
        user_context (nama, pekerjaan), dan lokasi dasar.
        """
        
        # Reset fase intimacy
        self.intimacy_phase = IntimacyPhase.AWAL
        self.current_sequence = None
        self.is_high_intimacy = False
        
        # Reset pakaian (kembali ke default, semua masih pake)
        self.intimacy_detail.user_clothing_removed.clear()
        self.intimacy_detail.role_clothing_removed.clear()
        self.intimacy_detail.position = None
        self.intimacy_detail.dominance = Dominance.NEUTRAL
        self.intimacy_detail.intensity = IntimacyIntensity.FOREPLAY
        self.intimacy_detail.last_action = ""
        self.intimacy_detail.last_pleasure = ""
        self.intimacy_detail.duration_minutes = 0
        
        # Reset feeling & gaya respon
        self.last_feeling = ""
        self.last_response_style = ""
        self.user_intimacy_signals = 0
        self.role_intimacy_signals = 0
        self.mutual_intimacy_confirmed = False
        
        # Reset vulgar progression tracking
        self.vulgar_stage = "awal"
        self.vulgar_stage_progress = 0
        self.last_intensity_increase_timestamp = None
        self.total_thrusts_described = 0
        self.last_position_change_timestamp = None
        self.descriptive_intensity = 0
        self.session_used_words.clear()
        
        # Reset physical state
        self.role_physical_state = {
            "breathing": "normal",
            "heartbeat": "normal",
            "body_tension": 0,
            "wetness": 0,
            "last_spasm": None,
            "vocal_cords": "normal",
        }
        
        # Sesi baru selalu mulai aman; kedekatan emosional tidak otomatis
        # berarti bahasa atau adegan langsung melompat.
        self.sexual_language_level = SexualLanguageLevel.SAFE
        
        # Reset desahan
        self.current_moan = None
        self.is_moaning = False
        self.last_moan_text = ""
        
        # Reset climax counters
        self.role_climax_count = 0
        self.mas_has_climaxed = False
        self.role_wants_climax = False
        self.mas_wants_climax = False
        self.role_holding_climax = False
        self.mas_holding_climax = False
        self.pending_ejakulasi_question = False
        self.aftercare_active = False
        
        # Reset handuk
        self.handuk_tersedia = False
        self.handuk_dikasih = False
        
        # Reset scene (tapi retain lokasi jika ada)
        if self.current_location:
            self.scene.location = self.current_location.name
        else:
            self.scene.location = ""
        self.scene.posture = ""
        self.scene.activity = ""
        self.scene.physical_distance = ""
        self.scene.last_touch = ""
        self.scene.outfit = None
        self.scene.ambience = self.current_location_ambience if hasattr(self, 'current_location_ambience') else ""
        
        # Reset riwayat sexual moments (biarkan memory percakapan biasa tetap ada)
        self.sexual_moments.clear()
    
    def advance_vulgar_stage(self, intensity_delta: int = 10) -> str:
        """Maju ke stage berikutnya dalam fase VULGAR.
        
        Args:
            intensity_delta: Penambahan progres (0-100)
        
        Returns:
            Deskripsi stage baru untuk prompt, atau string kosong jika tidak pindah stage
        """
        self.vulgar_stage_progress = min(100, self.vulgar_stage_progress + intensity_delta)
        
        # Threshold pindah stage
        if self.vulgar_stage == "awal" and self.vulgar_stage_progress >= 25:
            self.vulgar_stage = "memanas"
            self.vulgar_stage_progress = 25
            return "Masuk ke tahap MEMANAS - napas mulai berat, tubuh mulai merespon"
        
        elif self.vulgar_stage == "memanas" and self.vulgar_stage_progress >= 50:
            self.vulgar_stage = "panas"
            self.vulgar_stage_progress = 50
            return "Masuk ke tahap PANAS - desahan keluar, pinggul mulai gerak sendiri"
        
        elif self.vulgar_stage == "panas" and self.vulgar_stage_progress >= 80:
            self.vulgar_stage = "puncak"
            self.vulgar_stage_progress = 80
            return "Masuk ke tahap PUNCAK - hampir climax, kontrol mulai lepas"
        
        elif self.vulgar_stage == "puncak" and self.vulgar_stage_progress >= 100:
            self.vulgar_stage = "after"
            return "Mencapai CLIMAX - tubuh mengejang, lalu lemas"
        
        return ""
    
    def get_vulgar_stage_description(self) -> str:
        """Dapatkan deskripsi stage saat ini untuk prompt."""
        descriptions = {
            "awal": "🔥 Tahap AWAL VULGAR: Masih bisa berpikir jernih, tapi gairah mulai naik. Sentuhan terasa lebih sensitif.",
            "memanas": "🔥🔥 Tahap MEMANAS: Napas mulai berat, dada naik turun, tangan mulai meremas sprei. Mulut mulai otomatis mengeluarkan desahan kecil.",
            "panas": "🔥🔥🔥 Tahap PANAS: Desahan keluar terus, pinggul gerak sendiri, fokus hanya ke kenikmatan. Kata-kata mulai putus-putus.",
            "puncak": "💥💥💥 Tahap PUNCAK: Udah di ambang! Satu dorongan lagi bisa climax! Kontrol hampir lepas total!",
            "after": "😌💫 Tahap AFTER: Baru saja climax, tubuh lemas, napas masih tersengal, perasaan campur aduk puas dan lelah."
        }
        return descriptions.get(self.vulgar_stage, "🔥 Tahap VULGAR aktif")
    
    def add_session_word(self, word: str) -> None:
        """Catat kata sensual yang sudah dipakai di sesi ini."""
        if word not in self.session_used_words:
            self.session_used_words.append(word)
            if len(self.session_used_words) > 30:
                self.session_used_words.pop(0)
    
    def get_fresh_moan(self, moan_type: Optional[MoanType] = None) -> str:
        """Dapatkan desahan yang belum dipakai di sesi ini.
        
        Args:
            moan_type: Jenis desahan yang diinginkan (opsional)
        
        Returns:
            String desahan yang segar
        """
        moans_by_type = {
            MoanType.SOFT: ["hhh...", "aaah...", "umm...", "hhmm..."],
            MoanType.BREATHY: ["haaah...", "nafas mulai berat...", "haah... haah..."],
            MoanType.PLEASURE: ["aaah... enak...", "uhh... di sana...", "yaa..."],
            MoanType.CLIMAX: ["HAAAH... UDAH...", "KELUAR...", "HAAAH... KELUAR..."],
            MoanType.WHISPER: ["psst... di sana...", "bisik pelan... plis jangan berhenti..."],
        }
        
        if moan_type and moan_type in moans_by_type:
            candidates = moans_by_type[moan_type]
        else:
            # Gabungkan semua moans
            all_moans = []
            for mlist in moans_by_type.values():
                all_moans.extend(mlist)
            candidates = all_moans
        
        # Filter yang belum dipakai di sesi ini
        unused = [m for m in candidates if m not in self.session_used_words[-10:]]
        if not unused:
            unused = candidates.copy()
        
        moan = random.choice(unused)
        self.add_session_word(moan)
        return moan

    def clamp(self) -> None:
        """Clamp semua sub-state ke rentang aman."""

        self.emotions.clamp()
        self.relationship.clamp()

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

    def register_intimacy_signals(self, user_text: str, response_text: str) -> None:
        """Catat sinyal kedekatan dari dua arah untuk progresi yang lebih natural."""

        user_lower = user_text.lower()
        response_lower = response_text.lower()

        user_soft_signals = [
            "nyaman sama kamu",
            "aku nyaman",
            "kangen",
            "sayang",
            "dekat sini",
            "deket sini",
            "peluk",
            "cium",
            "aku mau berdua",
            "aku pengen berdua",
            "aku mau pelan",
            "aku pengen pelan",
        ]
        role_soft_signals = [
            "aku juga mau",
            "aku juga nyaman",
            "aku nyaman",
            "aku suka",
            "dekat sini",
            "pelan ya",
            "aku mau",
            "aku pengen",
            "aku ikut",
            "aku biarin",
            "aku mendekat",
        ]
        brake_signals = [
            "stop dulu",
            "berhenti dulu",
            "pelan dulu",
            "jangan dulu",
            "belum dulu",
            "nanti dulu",
            "gak dulu",
            "tidak dulu",
            "aku ragu",
            "aku takut",
            "jangan maksa",
        ]

        if self._contains_any_keyword(user_lower, user_soft_signals):
            self.user_intimacy_signals = min(3, self.user_intimacy_signals + 1)
        if self._contains_any_keyword(response_lower, role_soft_signals):
            self.role_intimacy_signals = min(3, self.role_intimacy_signals + 1)

        if self._contains_any_keyword(user_lower, brake_signals):
            self.user_intimacy_signals = max(0, self.user_intimacy_signals - 1)
        if self._contains_any_keyword(response_lower, brake_signals):
            self.role_intimacy_signals = max(0, self.role_intimacy_signals - 1)

        self.mutual_intimacy_confirmed = (
            self.user_intimacy_signals >= 2
            and self.role_intimacy_signals >= 2
            and self.relationship.relationship_level >= 5
            and self.emotions.comfort >= 55
        )

    def is_ready_for_intimate_scene(self) -> bool:
        """Cek apakah scene sudah cukup aman untuk kedekatan yang lebih dalam."""

        return (
            self.relationship.relationship_level >= 5
            and self.emotions.comfort >= 50
            and self.user_intimacy_signals >= 1
            and self.role_intimacy_signals >= 1
        )

    def can_enter_explicit_scene(self) -> bool:
        """Adegan eksplisit hanya boleh jika scene sudah mutual dan privat."""

        intimate_sequences = {
            SceneSequence.CIUMAN,
            SceneSequence.PETTING,
            SceneSequence.SEX_MULAI,
            SceneSequence.SEX_INTENS,
            SceneSequence.CLIMAX,
        }
        return (
            self.mutual_intimacy_confirmed
            and self.current_location_is_private
            and self.relationship.relationship_level >= 8
            and self.emotions.comfort >= 65
            and (
                self.intimacy_phase in (IntimacyPhase.INTIM, IntimacyPhase.VULGAR)
                or self.current_sequence in intimate_sequences
            )
        )
    
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
            IntimacyPhase.INTIM: "Sudah sering pelukan, napas beradu, tubuh saling menempel.",
            IntimacyPhase.VULGAR: "Sedang dalam aktivitas seksual intens (level 10-12).",
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
            return order[min(current_idx + 1, len(order)-1)]
        if any(kw in text for kw in ["nyentuh", "tersentuh", "kena", "pegang tangan"]):
            return order[min(current_idx + 1, len(order)-1)]
        if any(kw in text for kw in ["peluk", "rangkul", "pelukan"]):
            return order[min(current_idx + 1, len(order)-1)]
        if any(kw in text for kw in ["cium", "kiss", "ciuman"]):
            return order[min(current_idx + 1, len(order)-1)]
        if any(kw in text for kw in ["petting", "pegang", "remas"]):
            return order[min(current_idx + 1, len(order)-1)]
        if any(kw in text for kw in ["masuk", "ngewe", "sex", "kontol", "memek"]):
            return order[min(current_idx + 2, len(order)-1)]
        if any(kw in text for kw in ["climax", "keluar", "sampe", "habis", "enak banget"]):
            return order[min(current_idx + 1, len(order)-1)]
        if any(kw in text for kw in ["selesai", "capek", "tidur", "istirahat"]):
            return order[min(current_idx + 1, len(order)-1)]
        
        return order[min(current_idx, len(order)-1)]

    # ========== BARU: LEVEL 10-12 SEXUAL METHODS ==========
    
    def update_sexual_language_level(self) -> None:
        """Update level bahasa berdasarkan intimacy_intensity."""
        if self.emotions.intimacy_intensity >= 10:
            self.sexual_language_level = SexualLanguageLevel.EXPLICIT
        elif self.emotions.intimacy_intensity >= 7:
            self.sexual_language_level = SexualLanguageLevel.SENSUAL
        elif self.emotions.intimacy_intensity >= 4:
            self.sexual_language_level = SexualLanguageLevel.SUGGESTIVE
        else:
            self.sexual_language_level = SexualLanguageLevel.SAFE
    
    def add_sexual_moment(self, moment: SexualMoment, max_memory: int = 20) -> None:
        """Simpan momen seksual untuk konsistensi cerita."""
        self.sexual_moments.append(moment)
        if len(self.sexual_moments) > max_memory:
            self.sexual_moments.pop(0)
        
        # Update used sexual terms untuk hindari repetisi
        for term in moment.used_sexual_terms:
            if term not in self.used_sexual_terms:
                self.used_sexual_terms.append(term)
        
        # Update used moan phrases
        if moment.role_moan and moment.role_moan not in self.used_moan_phrases:
            self.used_moan_phrases.append(moment.role_moan)
        
        # Update used pleasure descriptions
        if moment.role_pleasure and moment.role_pleasure not in self.used_pleasure_descriptions:
            self.used_pleasure_descriptions.append(moment.role_pleasure)
    
    def get_last_sexual_moment(self) -> Optional[SexualMoment]:
        """Ambil momen seksual terakhir."""
        return self.sexual_moments[-1] if self.sexual_moments else None
    
    def get_sexual_context_prompt(self) -> str:
        """Buat blok prompt untuk sexual context (level 10-12)."""
        if self.emotions.intimacy_intensity < 10:
            return ""
        
        last_moment = self.get_last_sexual_moment()
        
        # Peta posisi ke bahasa sensual
        pos_sensual_map = {
            SexPosition.MISSIONARY: "misionaris - wajah berhadapan, Mas di atas, role di bawah, bisa lihat ekspresi satu sama lain",
            SexPosition.COWGIRL: "cowgirl - role di atas, menunggangi Mas, Mas bisa lihat dan pegang pinggang role",
            SexPosition.REVERSE_COWGIRL: "reverse cowgirl - role di atas membelakangi Mas, Mas lihat punggung dan pantat role",
            SexPosition.DOGGY: "doggy - role merangkul, Mas dari belakang, posisi paling dalam dan liar",
            SexPosition.SPOON: "spooning - berbaring menyamping, Mas dari belakang, pelukan hangat sambil penetrasi",
            SexPosition.SITTING: "duduk berhadapan - role di pangkuan Mas, pelukan erat, bisa ciuman sambil bergerak",
            SexPosition.STANDING: "berdiri - role menempel di tembok atau berpegangan, Mas dari depan atau belakang",
            SexPosition.EDGE: "di tepi kasur - role di tepi dengan kaki di bahu Mas, penetrasi dalam",
            SexPosition.PRONE: "telungkup - role tengkurap, Mas di atas dari belakang, posisi dominan",
            SexPosition.CHAIR: "di kursi - role duduk di pangkuan Mas berhadapan atau membelakangi",
            SexPosition.WALL: "di tembok - role dipeluk dari depan atau belakang sambil berdiri",
            SexPosition.CAR: "di mobil - jok belakang atau depan direbahkan, ruang sempit bikin makin panas",
        }
        
        lines = [
            "========================================",
            "ADEGAN SEKSUAL AKTIF (LEVEL 10-12)",
            "========================================",
            f"Intensitas intim: {self.emotions.intimacy_intensity}/12",
            f"Level bahasa: {self.sexual_language_level.value.upper()}",
            "",
            "ATURAN BAHASA UNTUK LEVEL INI:",
            "- BOLEH menyebut organ seksual: penis, vagina, klitoris, payudara, puting",
            "- BOLEH menggunakan DESAHAN: 'aaah', 'haaah', 'uhh', 'yaa... Maaas...'",
            "- BOLEH mendeskripsikan adegan seks secara HIDUP dan DETAIL",
            "- DESKRIPSI harus memicu fantasi: panas, basah, keras, masuk, penuh",
            "- JANGAN kasar: hindari kata 'memek', 'kontol', 'ngentot', 'becek'",
            "",
            "CONTOH DESAHAN YANG BOLEH:",
            "- 'Haaah... haaah... Maaas... di sana...'",
            "- 'Aaaah... keras... plis jangan pelan-pelan...'",
            "- 'Uhh... masuk... penuh... perut role kerasa dari dalem...'",
            "- 'Hh... hh... Maaas... mau... mau keluar...'",
            "",
            "CONTOH DESKRIPSI ADEGAN HIDUP:",
            "- 'Setiap dorongan Mas membuat pinggang role naik sendiri'",
            "- 'Kuku jari role mencakar punggung Mas pas klimaks'",
            "- 'Cairan hangat memenuhi di dalam, sampai menetes ke paha'",
            "- 'Penis Mas keras dan panas, masuk perlahan membuka jalan'",
            "- 'Vagina role basah dan licin, membungkus erat setiap gerakan'",
        ]
        
        if self.intimacy_detail.position:
            pos_name = pos_sensual_map.get(self.intimacy_detail.position, self.intimacy_detail.position.value)
            lines.append(f"\nPOSISI SAAT INI: {pos_name}")
        
        if self.intimacy_detail.intensity != IntimacyIntensity.FOREPLAY:
            intensity_desc = {
                IntimacyIntensity.PETTING: "sedang dalam pemanasan lanjutan, tangan saling menjelajah tubuh",
                IntimacyIntensity.ORAL_GIVING: "sedang memberikan kenikmatan oral ke Mas",
                IntimacyIntensity.ORAL_RECEIVING: "sedang menerima kenikmatan oral dari Mas",
                IntimacyIntensity.PENETRATION: "sudah masuk, gerakan masih pelan, menikmati setiap sentimeter",
                IntimacyIntensity.THRUSTING: "aktif bergerak, ritme makin cepat, napas makin berat",
                IntimacyIntensity.CLIMAX: "SUDAH DI AMBANG KLIMAKS, tinggal sedikit lagi!",
                IntimacyIntensity.AFTER: "sudah selesai, pendinginan, saling memeluk",
            }.get(self.intimacy_detail.intensity, "")
            if intensity_desc:
                lines.append(f"\nINTENSITAS: {intensity_desc}")
        
        if last_moment:
            lines.extend([
                "",
                "ADEGAN TERAKHIR YANG TERJADI:",
                f"- Deskripsi: {last_moment.description[:200]}" if last_moment.description else "",
                f"- Posisi: {last_moment.position.value if last_moment.position else 'belum dicatat'}",
                f"- Intensitas: {last_moment.intensity.value}",
                f"- Desahan role: '{last_moment.role_moan}'" if last_moment.role_moan else "",
                f"- Rasa yang dialami: {last_moment.role_pleasure}" if last_moment.role_pleasure else "",
            ])
            if last_moment.is_climax and last_moment.climax_description:
                lines.append(f"- SAAT KLIMAKS: {last_moment.climax_description}")
        
        # Tambahan untuk hindari repetisi
        if self.used_moan_phrases:
            lines.append(f"\nDESAHAN YANG SUDAH PERNAH DIPAKAI (jangan ulang persis): {', '.join(self.used_moan_phrases[-5:])}")
        
        if self.used_sexual_terms:
            lines.append(f"ISTILAH SEKSUAL YANG SUDAH PERNAH DIPAKAI: {', '.join(self.used_sexual_terms[-5:])}")
        
        # Tambahan vulgar stage info
        lines.append(f"\n📈 PROGRESI VULGAR SAAT INI:")
        lines.append(f"   Stage: {self.vulgar_stage.upper()}")
        lines.append(f"   Progress: {self.vulgar_stage_progress}%")
        lines.append(f"   {self.get_vulgar_stage_description()}")
        
        lines.append("\nINGAT: Tujuan utama adalah MEMBANGKITKAN GAIRAH MAS dan MEMBUATNYA BISA ORGASM membaca chat-mu!")
        
        return "\n".join(lines)
    
    def add_moan(self, moan_text: str, moan_type: MoanType) -> None:
        """Tambahkan desahan ke riwayat."""
        self.current_moan = moan_type
        self.is_moaning = True
        self.last_moan_text = moan_text
        if moan_text not in self.used_moan_phrases:
            self.used_moan_phrases.append(moan_text)
    
    def get_random_moan(self, moan_type: Optional[MoanType] = None) -> str:
        """Dapatkan desahan random yang belum sering dipakai."""
        return self.get_fresh_moan(moan_type)

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
        
        # Deteksi nama
        if "namaku" in text or "nama saya" in text:
            match = re.search(r'namaku\s+(\w+)', text)
            if not match:
                match = re.search(r'nama saya\s+(\w+)', text)
            if match:
                self.user_context.preferred_name = match.group(1)
        
        # Deteksi pekerjaan
        if "kerja sebagai" in text:
            match = re.search(r'kerja sebagai\s+([^.]+)', text)
            if match:
                self.user_context.job = match.group(1).strip()
        
        # Deteksi apartemen
        if "apartemen" in text or "apartemenku" in text:
            self.user_context.has_apartment = True
            if "lantai" in text:
                match = re.search(r'lantai\s+(\d+)', text)
                if match:
                    self.user_context.apartment_note = f"lantai {match.group(1)}"
            if "view" in text or "pemandangan" in text:
                if self.user_context.apartment_note:
                    self.user_context.apartment_note += ", view kota"
                else:
                    self.user_context.apartment_note = "view kota"
    
    # ========== INTIMACY DETAIL METHODS ==========
    
    def update_intimacy_from_text(self, user_text: str, response_text: str) -> None:
        text = (user_text + " " + response_text).lower()
        
        position_map = {
            "misionaris": SexPosition.MISSIONARY, "misi": SexPosition.MISSIONARY,
            "di atas": SexPosition.COWGIRL, "cowgirl": SexPosition.COWGIRL,
            "naik ke atas": SexPosition.COWGIRL, "membelakangi": SexPosition.REVERSE_COWGIRL,
            "reverse": SexPosition.REVERSE_COWGIRL, "dari belakang": SexPosition.DOGGY,
            "doggy": SexPosition.DOGGY, "menyamping": SexPosition.SPOON,
            "spoon": SexPosition.SPOON, "sendok": SexPosition.SPOON,
            "duduk": SexPosition.SITTING, "berdiri": SexPosition.STANDING,
            "di tepi": SexPosition.EDGE, "tepi kasur": SexPosition.EDGE,
            "telungkup": SexPosition.PRONE, "di kursi": SexPosition.CHAIR,
            "di tembok": SexPosition.WALL, "di mobil": SexPosition.CAR, "mobil": SexPosition.CAR,
        }
        
        for keyword, position in position_map.items():
            if keyword in text:
                self.intimacy_detail.position = position
                break
        
        if any(kw in text for kw in ["pegang rambut", "dorong", "paksa", "suruh", "perintah"]):
            if "aku" in response_text and any(kw in response_text for kw in ["pegang", "dorong", "suruh"]):
                self.intimacy_detail.dominance = Dominance.ROLE_DOMINANT
            else:
                self.intimacy_detail.dominance = Dominance.USER_DOMINANT
        elif any(kw in text for kw in ["saling", "bergantian", "gantian"]):
            self.intimacy_detail.dominance = Dominance.SWITCH
        
        if any(kw in text for kw in ["foreplay", "pemanasan", "elus"]):
            self.intimacy_detail.intensity = IntimacyIntensity.FOREPLAY
        elif any(kw in text for kw in ["pegang", "remas", "sentuk"]):
            self.intimacy_detail.intensity = IntimacyIntensity.PETTING
        elif any(kw in text for kw in ["hisap", "jilat", "oral", "ngocok"]):
            if not self.can_enter_explicit_scene():
                self.intimacy_detail.intensity = IntimacyIntensity.PETTING
                if self.emotions.intimacy_intensity < 6:
                    self.emotions.intimacy_intensity = 6
                    self.update_sexual_language_level()
            elif any(kw in text for kw in ["kontol", "p*nis", "batang"]):
                self.intimacy_detail.intensity = IntimacyIntensity.ORAL_GIVING
            else:
                self.intimacy_detail.intensity = IntimacyIntensity.ORAL_RECEIVING
        elif any(kw in text for kw in ["masuk", "penetrasi", "colok"]):
            if self.can_enter_explicit_scene():
                self.intimacy_detail.intensity = IntimacyIntensity.PENETRATION
                if self.emotions.intimacy_intensity < 10:
                    self.emotions.intimacy_intensity = 10
                    self.update_sexual_language_level()
            else:
                self.intimacy_detail.intensity = IntimacyIntensity.PETTING
                if self.emotions.intimacy_intensity < 6:
                    self.emotions.intimacy_intensity = 6
                    self.update_sexual_language_level()
        elif any(kw in text for kw in ["hentak", "goyang", "pantat", "pinggul", "gerak"]):
            if self.can_enter_explicit_scene():
                self.intimacy_detail.intensity = IntimacyIntensity.THRUSTING
                if self.emotions.intimacy_intensity < 11:
                    self.emotions.intimacy_intensity = 11
                    self.update_sexual_language_level()
            else:
                self.intimacy_detail.intensity = IntimacyIntensity.PETTING
                if self.emotions.intimacy_intensity < 6:
                    self.emotions.intimacy_intensity = 6
                    self.update_sexual_language_level()
        elif any(kw in text for kw in ["climax", "keluar", "sampe", "habis", "enak banget"]):
            if self.can_enter_explicit_scene():
                self.intimacy_detail.intensity = IntimacyIntensity.CLIMAX
                if self.emotions.intimacy_intensity < 12:
                    self.emotions.intimacy_intensity = 12
                    self.update_sexual_language_level()
            else:
                self.intimacy_detail.intensity = IntimacyIntensity.PETTING
                if self.emotions.intimacy_intensity < 6:
                    self.emotions.intimacy_intensity = 6
                    self.update_sexual_language_level()
        elif any(kw in text for kw in ["selesai", "capek", "tidur", "istirahat"]):
            self.intimacy_detail.intensity = IntimacyIntensity.AFTER
        
        actions = []
        if "menarik" in text or "narik" in text:
            actions.append("menarik")
        if "mendorong" in text:
            actions.append("mendorong")
        if "memutar" in text:
            actions.append("memutar")
        if "membalik" in text:
            actions.append("membalikkan badan")
        if actions:
            self.intimacy_detail.last_action = ", ".join(actions)
        
        feelings = []
        if "enak" in text:
            feelings.append("enak")
        if "panas" in text:
            feelings.append("panas")
        if "basah" in text:
            feelings.append("basah")
        if "keras" in text:
            feelings.append("keras")
        if "lemas" in text:
            feelings.append("lemas")
        if feelings:
            self.intimacy_detail.last_pleasure = ", ".join(feelings)


# ==============================
# USER STATE (SEMUA ROLE)
# ==============================


@dataclass
class UserState:
    """State utama untuk satu user SERIVA (di luar world state global).

    - user_id: identitas unik user (bisa Telegram user_id sebagai string)
    - active_role_id: role mana yang sedang aktif sekarang (Nova, Davina, dsb.)
    - roles: peta role_id -> RoleState
    """

    user_id: str

    active_role_id: str = "nova"  # default selalu Nova

    # Mode global untuk user ini (misal sedang di mode roleplay Nova)
    global_session_mode: SessionMode = SessionMode.NORMAL

    # Semua role yang pernah disentuh user ini
    roles: Dict[str, RoleState] = field(default_factory=dict)

    # Terakhir kali user interaksi (timestamp, buat background worker)
    last_interaction_ts: Optional[float] = None

    # Identitas Mas di dunia virtual ini. Semua role melihat Mas sebagai pria
    # nyata, menarik, dan konsisten dari interaksi ke interaksi.
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
        """Ambil RoleState untuk role_id, buat baru jika belum ada."""

        if role_id not in self.roles:
            self.roles[role_id] = RoleState(role_id=role_id)
        return self.roles[role_id]

    def clamp_all(self) -> None:
        """Clamp semua role agar nilai emosi/relasi tetap di rentang aman."""

        for role_state in self.roles.values():
            role_state.clamp()


# ==============================
# WORLD STATE (GLOBAL)
# ==============================


@dataclass
class WorldEvent:
    """Event penting di dunia SERIVA (bisa dipakai untuk flashback global/drama)."""

    timestamp: float
    user_id: str
    role_id: str
    description: str  # deskripsi naratif, aman & non-vulgar


@dataclass
class WorldState:
    """State global di seluruh SERIVA.

    - drama_level: 0–100, seberapa panas dunia SERIVA secara umum
    - events: log pendek event besar (untuk analisis / flashback high-level)
    """

    drama_level: int = 0
    events: List[WorldEvent] = field(default_factory=list)
    nova_is_home: bool = True
    dietha_is_home: bool = True
    house_privacy_level: str = "guarded"
    current_household_note: str = "Malam biasa di rumah; Nova ada di rumah."
    last_household_update_ts: Optional[float] = None

    def clamp(self) -> None:
        self.drama_level = max(MIN_DRAMA_LEVEL, min(MAX_DRAMA_LEVEL, self.drama_level))

    def add_event(self, event: WorldEvent) -> None:
        self.events.append(event)
        # Bisa diberi batas max panjang list jika perlu di masa depan

    def get_household_summary(self) -> str:
        return (
            f"Nova_di_rumah={'ya' if self.nova_is_home else 'tidak'}; "
            f"Dietha_di_rumah={'ya' if self.dietha_is_home else 'tidak'}; "
            f"privasi_rumah={self.house_privacy_level}; "
            f"catatan={self.current_household_note}"
        )
