"""Global constants for SERIVA configuration.

Berisi:
- ID role resmi
- Metadata dasar role (nama tampilan, alias, kategori)
- Default batasan sistem (history, level, dsb.)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Literal


# ==============================
# ROLE DEFINITIONS
# ==============================

RoleCategory = Literal[
    "PRIMARY_PARTNER",      # Nova
    "IPAR",                 # Ipar Tasha
    "TEMAN_KANTOR",         # Musdalifah / Ipeh
    "TEMAN_LAMA",           # Widya
    "WANITA_BERSUAMI",      # Siska
    "TERAPIS_PIJAT",        # Aghnia, Munira
    "TEMAN_SPESIAL",        # Davina, Sallsa
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
ROLE_ID_NOVA = "nova"
ROLE_ID_IPAR_TASHA = "ipar_tasha"
ROLE_ID_TEMAN_KANTOR_IPEH = "teman_kantor_ipeh"
ROLE_ID_TEMAN_LAMA_WIDYA = "teman_lama_widya"
ROLE_ID_WANITA_BERSUAMI_SISKA = "wanita_bersuami_siska"
ROLE_ID_TERAPIS_AGHIA = "terapis_aghia"
ROLE_ID_TERAPIS_MUNIRA = "terapis_munira"
ROLE_ID_TEMAN_SPESIAL_DAVINA = "teman_spesial_davina"
ROLE_ID_TEMAN_SPESIAL_SALLSA = "teman_spesial_sallsa"


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
    ROLE_ID_TEMAN_SPESIAL_DAVINA: RoleInfo(
        role_id=ROLE_ID_TEMAN_SPESIAL_DAVINA,
        display_name="Davina",
        alias="Davina",
        category="TEMAN_SPESIAL",
    ),
    ROLE_ID_TEMAN_SPESIAL_SALLSA: RoleInfo(
        role_id=ROLE_ID_TEMAN_SPESIAL_SALLSA,
        display_name="Sallsa",
        alias="Sallsa",
        category="TEMAN_SPESIAL",
    ),
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
    "VULGAR": 0.85,
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
        elif info.category == "TEMAN_SPESIAL":
            # Bedakan sedikit via alias di layer lain jika mau (spesial vs manja)
            label = f"Teman malam spesial ({info.display_name})"
        else:
            label = info.display_name

        summaries.append({
            "role_id": role_id,
            "label": label,
        })

    return summaries
