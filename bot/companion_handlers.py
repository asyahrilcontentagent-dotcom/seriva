"""Handler ringkas untuk mode companion 4 role."""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from bot.handlers import require_admin
from core.orchestrator import Orchestrator


def companion_start_handler(orchestrator: Orchestrator, admin_id: str):
    @require_admin(admin_id)
    async def _handler(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        chat = update.effective_chat
        if chat is None:
            return
        await chat.send_message(
            "Halo Mas, companion mode aktif.\n\n"
            "Role aktif sekarang cuma 4:\n"
            "- /role -> lihat daftar role\n"
            "- /role <id> -> pindah role\n"
            "- /status -> lihat state aktif\n"
            "- /pause /resume -> jeda atau lanjutkan scene\n"
            "- /cooldown -> balikin tensi ke fase dekat\n"
            "- /batal -> tutup sesi khusus\n"
            "- /flashback -> panggil momen yang pernah kebangun\n"
            "- /offline -> balik ke tatap muka dari chat/call/vps"
        )

    return _handler


def companion_help_handler(orchestrator: Orchestrator, admin_id: str):
    @require_admin(admin_id)
    async def _handler(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        chat = update.effective_chat
        if chat is None:
            return
        await chat.send_message(
            "Command companion:\n"
            "- /role -> daftar 4 role aktif\n"
            "- /role ipar_tasha -> Dietha\n"
            "- /role teman_kantor_ipeh -> Ipeh\n"
            "- /role teman_lama_widya -> Widya\n"
            "- /role wanita_bersuami_siska -> Siska\n"
            "- /status -> ringkasan emosi, scene, dan intimacy aktif\n"
            "- /pause /resume -> jeda atau lanjutkan scene\n"
            "- /cooldown -> turunkan tensi tanpa reset hubungan\n"
            "- /flashback -> panggil kenangan yang masih nyambung\n"
            "- /offline -> reset mode komunikasi ke tatap muka\n"
            "- /batal /end /close -> tutup sesi khusus"
        )

    return _handler


def companion_status_handler(orchestrator: Orchestrator, admin_id: str):
    @require_admin(admin_id)
    async def _handler(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        chat = update.effective_chat
        user = update.effective_user
        if chat is None or user is None:
            return

        user_state = orchestrator._load_or_init_user_state(str(user.id))
        role_state = user_state.get_or_create_role_state(user_state.active_role_id)

        e = role_state.emotions
        r = role_state.relationship
        s = role_state.scene
        intimacy = role_state.intimacy_detail

        role_display = getattr(role_state, "role_display_name", "") or role_state.role_id
        location = getattr(role_state, "current_location_name", "") or getattr(s, "location", None) or "belum ditentukan"
        privacy = "privat" if getattr(role_state, "current_location_is_private", False) else "publik/semi-private"
        mode = getattr(role_state, "communication_mode", None) or "tatap muka langsung"
        role_removed = ", ".join(intimacy.role_clothing_removed) or "-"
        user_removed = ", ".join(intimacy.user_clothing_removed) or "-"
        position = getattr(intimacy.position, "value", "-") if intimacy.position else "-"
        intensity = getattr(intimacy.intensity, "value", "-") if intimacy.intensity else "-"
        sequence = getattr(role_state.current_sequence, "value", "-") if role_state.current_sequence else "-"

        lines = [
            f"{role_display} aktif",
            "",
            "Emosi & hubungan",
            f"- Level hubungan: {r.relationship_level}/12",
            f"- Mood: {e.mood.value}",
            f"- Love: {e.love}",
            f"- Kangen: {e.longing}",
            f"- Nyaman: {e.comfort}",
            f"- Cemburu: {e.jealousy}",
            f"- Intimacy: {e.intimacy_intensity}/12",
            "",
            "Scene",
            f"- Fase: {role_state.intimacy_phase.value}",
            f"- Sequence: {sequence}",
            f"- Lokasi: {location} ({privacy})",
            f"- Aktivitas: {getattr(s, 'activity', None) or '-'}",
            f"- Postur: {getattr(s, 'posture', None) or '-'}",
            f"- Suasana: {getattr(s, 'ambience', None) or '-'}",
            f"- Jarak: {getattr(s, 'physical_distance', None) or '-'}",
            f"- Sentuhan: {getattr(s, 'last_touch', None) or '-'}",
            f"- Mode komunikasi: {mode}",
            "",
            "Intimacy state",
            f"- Posisi: {position}",
            f"- Intensitas: {intensity}",
            f"- Aksi terakhir: {getattr(intimacy, 'last_action', None) or '-'}",
            f"- Perasaan terakhir: {getattr(intimacy, 'last_pleasure', None) or '-'}",
            f"- Pakaian Mas yang sudah lepas: {user_removed}",
            f"- Pakaian role yang sudah lepas: {role_removed}",
        ]

        await chat.send_message("\n".join(lines))

    return _handler
