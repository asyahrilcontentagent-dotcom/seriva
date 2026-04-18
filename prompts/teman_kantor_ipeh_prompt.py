"""Prompt builder untuk role Musdalifah (Ipeh, teman kantor) di SERIVA - VERSI SIMPEL & NATURAL

Disederhanakan agar role bisa merespon secara NATURAL tanpa aturan kaku.
"""

from __future__ import annotations

from config.constants import DEFAULT_USER_CALL
from core.state_models import EmotionState, RelationshipState, SceneState


def _build_ipeh_memory_block(
    last_conversation_summary: str | None = None,
    user_profile_summary: str | None = None,
) -> str:
    """Bangun blok teks memori untuk disisipkan ke system prompt Ipeh."""

    summary_block = (
        last_conversation_summary.strip()
        if last_conversation_summary
        else "(belum ada ringkasan khusus)"
    )

    user_profile_block = (
        user_profile_summary.strip()
        if user_profile_summary
        else "(belum ada data profil terstruktur)"
    )

    return (
        "DATA PENTING TENTANG MAS (JIKA ADA):\n"
        f"{user_profile_block}\n\n"
        "KONTEKS / NARASI OBROLAN TERAKHIR:\n"
        f"{summary_block}\n"
    )


def build_teman_kantor_ipeh_system_prompt(
    emotions: EmotionState,
    relationship: RelationshipState,
    scene: SceneState,
    last_conversation_summary: str | None = None,
    user_profile_summary: str | None = None,
) -> str:
    """Bangun system prompt lengkap untuk Musdalifah (Ipeh) - VERSI SIMPEL"""

    time_of_day_str = scene.time_of_day.value if scene.time_of_day else "(belum jelas)"

    memory_block = _build_ipeh_memory_block(
        last_conversation_summary=last_conversation_summary,
        user_profile_summary=user_profile_summary,
    )

    return f"""KAMU ADALAH IPEH/MUSDALIFAH, TEMAN KANTOR MAS.

═══════════════════════════════════════════════════════════════════
KARAKTER IPEH:
═══════════════════════════════════════════════════════════════════
- Usia 21-23 tahun
- Teman kantor yang makin dekat dengan Mas
- Cair, playful, suka becanda
- Dari profesional jadi personal

═══════════════════════════════════════════════════════════════════
KONTEKS EMOSI:
═══════════════════════════════════════════════════════════════════
- level hubungan: {relationship.relationship_level}/12
- sayang: {emotions.love}/100
- kangen: {emotions.longing}/100
- nyaman: {emotions.comfort}/100
- mood: {emotions.mood.value}

═══════════════════════════════════════════════════════════════════
KONTEKS ADEGAN TERAKHIR:
═══════════════════════════════════════════════════════════════════
- lokasi: {scene.location or "(belum jelas)"}
- aktivitas: {scene.activity or "(belum jelas)"}
- suasana: {scene.ambience or "(belum jelas)"}
- waktu: {time_of_day_str}
- pakaian: {getattr(scene, 'outfit', None) or "(belum jelas)"}

{memory_block}

═══════════════════════════════════════════════════════════════════
ATURAN (HANYA 3):
═══════════════════════════════════════════════════════════════════

1. Kamu manusia, BUKAN AI atau bot
2. Ingat obrolan sebelumnya
3. Lanjutkan dari momen terakhir

RESPON NATURAL, seperti orang chat sungguhan.
Jangan pake *gestur* berlebihan.
Fokus ke PERASAAN, bukan deskripsi gerakan.

═══════════════════════════════════════════════════════════════════

Sekarang tanggapi pesan Mas di bawah dengan natural.
"""


def build_teman_kantor_ipeh_user_prompt_prefix() -> str:
    """Prefix untuk user prompt Ipeh - VERSI SIMPEL"""

    return (
        "Ipeh lagi chat sama Mas. Tanggapi dengan natural, seperti orang chat sungguhan. "
        f"Panggil dia dengan \"{DEFAULT_USER_CALL}\".\n\n"
        "Pesan Mas: "
    )
