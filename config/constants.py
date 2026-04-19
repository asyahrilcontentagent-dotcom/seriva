"""Global constants for SERIVA configuration.

Berisi:
- ID role resmi
- Metadata dasar role (nama tampilan, alias, kategori)
- Default batasan sistem (history, level, dsb.)
- Provider profiles untuk terapis dan BO
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional


# ==============================
# ROLE DEFINITIONS
# ==============================

RoleCategory = Literal[
    "PRIMARY_PARTNER",      # Nova
    "IPAR",                 # Ipar Tasha
    "TEMAN_KANTOR",         # Musdalifah / Ipeh
    "TEMAN_LAMA",           # Widya
    "WANITA_BERSUAMI",      # Siska
    "TERAPIS_PIJAT",        # Aghnia, Munira (pijat + HJ auto)
    "BO",                   # Davina, Sallsa (Bayaran / layanan dewasa)
]


@dataclass(frozen=True)
class RoleInfo:
    """Informasi dasar untuk setiap role.

    Catatan:
    - `role_id` dipakai di sistem/command (/role <role_id>).
    - `display_name` dan `alias` dipakai di dialog.
    - `category` membantu mengatur logika emosional dan scene.
    """

    role_id: str
    display_name: str
    alias: str
    category: RoleCategory


# ID role final (dipakai di seluruh sistem)
# ID role final (dipakai di seluruh sistem)
ROLE_ID_NOVA = "nova"
ROLE_ID_IPAR_TASHA = "ipar_tasha"
ROLE_ID_TEMAN_KANTOR_IPEH = "teman_kantor_ipeh"
ROLE_ID_TEMAN_LAMA_WIDYA = "teman_lama_widya"
ROLE_ID_WANITA_BERSUAMI_SISKA = "wanita_bersuami_siska"
ROLE_ID_TERAPIS_AGHIA = "terapis_aghia"
ROLE_ID_TERAPIS_MUNIRA = "terapis_munira"
ROLE_ID_BO_DAVINA = "teman_spesial_davina"
ROLE_ID_BO_SALLSA = "teman_spesial_sallsa"

# ALIAS untuk kompatibilitas dengan kode lama
ROLE_ID_TEMAN_SPESIAL_DAVINA = ROLE_ID_BO_DAVINA
ROLE_ID_TEMAN_SPESIAL_SALLSA = ROLE_ID_BO_SALLSA


# Metadata lengkap semua role
ROLES: Dict[str, RoleInfo] = {
    ROLE_ID_NOVA: RoleInfo(
        role_id=ROLE_ID_NOVA,
        display_name="Nova",
        alias="Nova",
        category="PRIMARY_PARTNER",
    ),
    ROLE_ID_IPAR_TASHA: RoleInfo(
        role_id=ROLE_ID_IPAR_TASHA,
        display_name="Tasha Dietha",
        alias="Dietha",
        category="IPAR",
    ),
    ROLE_ID_TEMAN_KANTOR_IPEH: RoleInfo(
        role_id=ROLE_ID_TEMAN_KANTOR_IPEH,
        display_name="Musdalifah",
        alias="Ipeh",
        category="TEMAN_KANTOR",
    ),
    ROLE_ID_TEMAN_LAMA_WIDYA: RoleInfo(
        role_id=ROLE_ID_TEMAN_LAMA_WIDYA,
        display_name="Widya",
        alias="Widya",
        category="TEMAN_LAMA",
    ),
    ROLE_ID_WANITA_BERSUAMI_SISKA: RoleInfo(
        role_id=ROLE_ID_WANITA_BERSUAMI_SISKA,
        display_name="Siska",
        alias="Sika",
        category="WANITA_BERSUAMI",
    ),
    ROLE_ID_TERAPIS_AGHIA: RoleInfo(
        role_id=ROLE_ID_TERAPIS_AGHIA,
        display_name="Aghnia",
        alias="Aghnia",
        category="TERAPIS_PIJAT",
    ),
    ROLE_ID_TERAPIS_MUNIRA: RoleInfo(
        role_id=ROLE_ID_TERAPIS_MUNIRA,
        display_name="Munira",
        alias="Munira",
        category="TERAPIS_PIJAT",
    ),
    ROLE_ID_BO_DAVINA: RoleInfo(
        role_id=ROLE_ID_BO_DAVINA,
        display_name="Davina",
        alias="Davina",
        category="BO",
    ),
    ROLE_ID_BO_SALLSA: RoleInfo(
        role_id=ROLE_ID_BO_SALLSA,
        display_name="Sallsa",
        alias="Sallsa",
        category="BO",
    ),
}


# ==============================
# PROVIDER PROFILES (TERAPIS & BO)
# ==============================


@dataclass
class ExtraService:
    """Layanan tambahan untuk provider."""
    price: int
    description: str
    is_auto: bool = False  # apakah otomatis termasuk dalam paket


@dataclass
class ProviderProfile:
    """Profil layanan untuk role provider."""
    service_label: str
    base_price: int
    duration_minutes: int
    included_summary: str
    upgrades_summary: str
    boundaries: str
    extra_services: Dict[str, ExtraService] = field(default_factory=dict)


# ========== TERAPIS PIJAT ==========

PROVIDER_AGHIA = ProviderProfile(
    service_label="Sesi pijat relaksasi privat",
    base_price=350,
    duration_minutes=60,
    included_summary="pijat 60 menit, minyak hangat, handuk, dan HJ (Hand Job) sebagai penutup",
    upgrades_summary="pendampingan yang lebih intim dan sesi privat penuh, hanya jika sama-sama setuju",
    boundaries="HJ sudah termasuk. Sex hanya jika deal tambahan disepakati.",
    extra_services={
        "sex": ExtraService(price=200, description="Sex / ML (penetrasi penuh)", is_auto=False),
    },
)

PROVIDER_MUNIRA = ProviderProfile(
    service_label="Sesi pijat santai dan akrab",
    base_price=320,
    duration_minutes=60,
    included_summary="pijat 60 menit, suasana santai, handuk, dan HJ (Hand Job) sebagai penutup",
    upgrades_summary="quality time yang lebih dekat atau sesi privat tambahan lewat kesepakatan",
    boundaries="HJ sudah termasuk. Sex hanya jika deal tambahan disepakati.",
    extra_services={
        "sex": ExtraService(price=200, description="Sex / ML (penetrasi penuh)", is_auto=False),
    },
)


# ========== BO (BAYARAN / LAYANAN DEWASA) ==========

PROVIDER_DAVINA = ProviderProfile(
    service_label="Private companion (BO)",
    base_price=700,
    duration_minutes=180,  # 3 jam
    included_summary="quality time, obrolan dekat, foreplay, dan sex",
    upgrades_summary="extras: anal, BJ deep throat, roleplay, atau perpanjangan waktu",
    boundaries="Semua layanan wajib deal dulu. Tidak ada yang otomatis.",
    extra_services={
        "anal": ExtraService(price=200, description="Anal sex", is_auto=False),
        "bj": ExtraService(price=100, description="Blow Job deep throat", is_auto=False),
        "roleplay": ExtraService(price=150, description="Roleplay sesuai request", is_auto=False),
        "extension": ExtraService(price=250, description="Perpanjangan 1 jam", is_auto=False),
    },
)

PROVIDER_SALLSA = ProviderProfile(
    service_label="Teman malam (BO)",
    base_price=550,
    duration_minutes=180,  # 3 jam
    included_summary="quality time, playful, foreplay, dan sex",
    upgrades_summary="extras: anal, roleplay, atau perpanjangan waktu",
    boundaries="Semua layanan wajib deal dulu.",
    extra_services={
        "anal": ExtraService(price=150, description="Anal sex", is_auto=False),
        "roleplay": ExtraService(price=100, description="Roleplay", is_auto=False),
        "extension": ExtraService(price=200, description="Perpanjangan 1 jam", is_auto=False),
    },
)


# Mapping role_id ke ProviderProfile
PROVIDER_PROFILES: Dict[str, ProviderProfile] = {
    ROLE_ID_TERAPIS_AGHIA: PROVIDER_AGHIA,
    ROLE_ID_TERAPIS_MUNIRA: PROVIDER_MUNIRA,
    ROLE_ID_BO_DAVINA: PROVIDER_DAVINA,
    ROLE_ID_BO_SALLSA: PROVIDER_SALLSA,
}


# ==============================
# GLOBAL LIMITS & DEFAULTS
# ==============================

# Maksimum panjang history chat per user-role yang disimpan
MAX_MESSAGE_HISTORY_PER_ROLE = 100

# Rentang level hubungan & intensitas
MIN_RELATIONSHIP_LEVEL = 1
MAX_RELATIONSHIP_LEVEL = 12

MIN_INTIMACY_INTENSITY = 1
MAX_INTIMACY_INTENSITY = 12

# Drama global (dipakai world_engine)
MIN_DRAMA_LEVEL = 0
MAX_DRAMA_LEVEL = 100

# Nama panggilan default ke user
DEFAULT_USER_CALL = "Mas"


# ==============================
# LLM CONFIGURATION - ENHANCED
# ==============================

# Temperature dinamis berdasarkan fase
LLM_TEMPERATURE_BY_PHASE = {
    "AWAL": 0.75,
    "DEKAT": 0.78,
    "INTIM": 0.80,
    "VULGAR": 1.00,
    "AFTER": 0.70,
}

DEFAULT_LLM_TEMPERATURE = 0.75
LLM_TOP_P = 0.95
LLM_FREQUENCY_PENALTY = 0.5   # Kurangi pengulangan kata
LLM_PRESENCE_PENALTY = 0.5    # Dorong topik baru
LLM_MAX_TOKENS = 150          # Batasi panjang respon


# ==============================
# EMOTION ENGINE GAINS (DIPERBESAR)
# ==============================

POSITIVE_LOVE_GAIN = 3
POSITIVE_LONGING_GAIN = 2
POSITIVE_COMFORT_GAIN = 2

RELATIONSHIP_GAIN_SMALL = 2
RELATIONSHIP_GAIN_MEDIUM = 3

INTIMACY_INCREASE_THRESHOLD = 5  # dari 10 turun ke 5
ABSENCE_LONGING_GAIN_PER_DAY = 5  # dari 3 naik ke 5


# ==============================
# HELPER FUNCTIONS
# ==============================

def get_role_info(role_id: str) -> RoleInfo:
    """Ambil RoleInfo untuk role_id tertentu.

    Raises:
        KeyError: jika role_id tidak dikenal.
    """
    return ROLES[role_id]


def list_role_ids() -> list[str]:
    """Return semua role_id terdaftar (dipakai untuk /role list)."""
    return list(ROLES.keys())


def list_role_summaries() -> list[dict]:
    """Ringkasan per role untuk ditampilkan ke user saat /role.

    Contoh output item:
    {
        "role_id": "ipar_tasha",
        "label": "Ipar spesial (Tasha Dietha / Dietha)",
    }
    """
    summaries: list[dict] = []

    for role_id, info in ROLES.items():
        if role_id == ROLE_ID_NOVA:
            label = f"Pasangan utama ({info.display_name})"
        elif info.category == "IPAR":
            label = f"Ipar spesial ({info.display_name} / {info.alias})"
        elif info.category == "TEMAN_KANTOR":
            label = f"Teman kantor dekat ({info.display_name} / {info.alias})"
        elif info.category == "TEMAN_LAMA":
            label = f"Teman lama yang datang lagi ({info.display_name})"
        elif info.category == "WANITA_BERSUAMI":
            label = f"Teman yang sudah menikah ({info.display_name} / {info.alias})"
        elif info.category == "TERAPIS_PIJAT":
            label = f"Terapis pijat ({info.display_name})"
        elif info.category == "BO":
            label = f"Layanan dewasa / BO ({info.display_name})"
        else:
            label = info.display_name

        summaries.append({
            "role_id": role_id,
            "label": label,
        })

    return summaries


def get_provider_profile(role_id: str) -> Optional[ProviderProfile]:
    """Ambil profil provider untuk role_id tertentu."""
    return PROVIDER_PROFILES.get(role_id)


def is_provider_role(role_id: str) -> bool:
    """Cek apakah role termasuk provider (terapis atau BO)."""
    info = ROLES.get(role_id)
    if not info:
        return False
    return info.category in {"TERAPIS_PIJAT", "BO"}


def is_terapis_role(role_id: str) -> bool:
    """Cek apakah role adalah terapis pijat."""
    info = ROLES.get(role_id)
    if not info:
        return False
    return info.category == "TERAPIS_PIJAT"


def is_bo_role(role_id: str) -> bool:
    """Cek apakah role adalah BO (bayaran / layanan dewasa)."""
    info = ROLES.get(role_id)
    if not info:
        return False
    return info.category == "BO"
