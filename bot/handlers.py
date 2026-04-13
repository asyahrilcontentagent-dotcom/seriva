"""Telegram handlers for SERIVA bot.

Menghubungkan Telegram update dengan Orchestrator SERIVA.
"""

from __future__ import annotations

import logging
import time
from typing import Callable, Awaitable, TypeVar, ParamSpec

from telegram import Update
from telegram.ext import ContextTypes

from config.constants import list_role_summaries, ROLE_ID_NOVA
from core.orchestrator import Orchestrator, OrchestratorInput, OrchestratorOutput
from core.state_models import SessionMode

logger = logging.getLogger(__name__)

PROCESSED_UPDATES = set()
P = ParamSpec("P")
R = TypeVar("R")



# ==============================
# HELPER: ADMIN CHECK
# ==============================


def is_authorized_user(update: Update, admin_id: str) -> bool:
    user = update.effective_user
    if user is None:
        return False
    return str(user.id) == str(admin_id)


def require_admin(admin_id: str) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """Decorator sederhana untuk memblokir non-admin (async-compatible)."""

    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:  # type: ignore[override]
            # Expect pola (update, context, ...)
            update: Update = args[0]
            context: ContextTypes.DEFAULT_TYPE = args[1]

            if not is_authorized_user(update, admin_id):
                chat = update.effective_chat
                if chat is not None:
                    await chat.send_message(
                        "Maaf, bot ini hanya bisa dipakai oleh admin yang ditentukan."
                    )
                # type: ignore[return-value]
                return None

            return await func(*args, **kwargs)

        return wrapper

    return decorator


# ==============================
# HANDLER COMMAND DASAR
# ==============================


def start_handler(orchestrator: Orchestrator, admin_id: str):
    @require_admin(admin_id)
    async def _handler(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        chat = update.effective_chat
        if chat is None:
            return
        await chat.send_message(
            "Halo Mas, ini SERIVA.\n\n"
            "Ketik aja seperti ngobrol biasa, atau pakai command:\n"
            "- /nova â†’ balik ke Nova\n"
            "- /role â†’ lihat daftar role\n"
            "- /role <id> â†’ pindah ke role tertentu\n"
            "- /pause â†’ pause sesi intens saat ini\n"
            "- /resume â†’ lanjutkan sesi yang di-pause\n"
            "- /batal, /end, /close â†’ akhiri sesi khusus & balik ke chat biasa\n"
            "- /status â†’ lihat ringkasan perasaan & adegan role aktif\n"
            "- /flashback â†’ minta role cerita ulang momen indah kalian\n"
            "- /nego <harga>, /deal, /mulai â†’ alur khusus untuk terapis & teman spesial"
        )

    return _handler


def help_handler(orchestrator: Orchestrator, admin_id: str):
    @require_admin(admin_id)
    async def _handler(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        chat = update.effective_chat
        if chat is None:
            return
        await chat.send_message(
            "Daftar command SERIVA:\n"
            "- /nova â†’ ngobrol dengan Nova (pasangan utama)\n"
            "- /role â†’ lihat daftar role yang tersedia\n"
            "- /role <id> â†’ pindah ke role tertentu (misal: /role teman_spesial_davina)\n"
            "- /pause â†’ pause sesi intens saat ini (roleplay/provider)\n"
            "- /resume â†’ lanjutkan sesi yang di-pause dari posisi terakhir\n"
            "- /batal, /end, atau /close â†’ akhiri sesi khusus dan kembali ke mode normal\n"
            "- /status â†’ lihat ringkasan perasaan & adegan role aktif\n"
            "- /flashback â†’ minta role cerita ulang satu momen indah/khas dengan Mas\n"
            "- /nego <harga> â†’ nego harga dengan terapis/teman spesial aktif\n"
            "- /deal â†’ konfirmasi setelah nego\n"
            "- /mulai â†’ mulai sesi setelah /deal"
        )

    return _handler


# ==============================
# HANDLER ROLE LIST & SWITCH
# ==============================


def role_list_handler(orchestrator: Orchestrator, admin_id: str):
    """/role tanpa argumen: tampilkan daftar role."""

    @require_admin(admin_id)
    async def _handler(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        chat = update.effective_chat
        if chat is None:
            return

        summaries = list_role_summaries()
        lines = ["Role yang tersedia:"]
        for item in summaries:
            lines.append(f"- {item['role_id']}: {item['label']}")

        lines.append("\nGunakan /role <id> untuk pindah ke role tertentu.")

        await chat.send_message("\n".join(lines))

    return _handler


def set_nova_handler(orchestrator: Orchestrator, admin_id: str):
    """/nova: paksa role aktif ke Nova."""

    @require_admin(admin_id)
    async def _handler(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        chat = update.effective_chat
        user = update.effective_user
        if chat is None or user is None:
            return

        user_state = orchestrator._load_or_init_user_state(str(user.id))  # type: ignore[attr-defined]
        user_state.active_role_id = ROLE_ID_NOVA
        orchestrator._save_all(user_state, orchestrator._load_or_init_world_state())  # type: ignore[attr-defined]

        await chat.send_message("Sekarang kamu lagi ngobrol sama Nova, Mas.")

    return _handler


def set_role_handler(orchestrator: Orchestrator, admin_id: str):
    """/role <id>: pindah role aktif."""

    @require_admin(admin_id)
    async def _handler(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        chat = update.effective_chat
        user = update.effective_user
        if chat is None or user is None:
            return

        args = context.args or []
        if not args:
            await chat.send_message(
                "Contoh: /role teman_spesial_davina.\n"
                "Ketik /role tanpa argumen untuk lihat daftar role."
            )
            return

        role_id = args[0].strip()

        summaries = list_role_summaries()
        valid_ids = {item["role_id"] for item in summaries}
        if role_id not in valid_ids:
            await chat.send_message(
                "Role tidak ditemukan. Ketik /role untuk lihat daftar role yang ada."
            )
            return

        user_state = orchestrator._load_or_init_user_state(str(user.id))  # type: ignore[attr-defined]
        user_state.active_role_id = role_id
        orchestrator._save_all(user_state, orchestrator._load_or_init_world_state())  # type: ignore[attr-defined]

        label = next((item["label"] for item in summaries if item["role_id"] == role_id), role_id)
        await chat.send_message(f"Sekarang kamu lagi sama {label}.")

    return _handler


# ==============================
# HANDLER END / STATUS
# ==============================


def end_session_handler(orchestrator: Orchestrator, admin_id: str):
    """/batal, /end, atau /close: akhiri sesi khusus (pakai logika Orchestrator)."""

    @require_admin(admin_id)
    async def _handler(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        chat = update.effective_chat
        user = update.effective_user
        if chat is None or user is None:
            return

        raw_text = update.effective_message.text if update.effective_message and update.effective_message.text else "/batal"
        normalized = raw_text.split("@", 1)[0].strip().lower()
        command_name = normalized.lstrip("/").split(None, 1)[0] or "batal"

        inp = OrchestratorInput(
            user_id=str(user.id),
            text=raw_text,
            timestamp=time.time(),
            is_command=True,
            command_name=command_name,
        )
        out: OrchestratorOutput = orchestrator.handle_input(inp)
        await chat.send_message(out.reply_text)

    return _handler


def status_handler(orchestrator: Orchestrator, admin_id: str):
    """/status: tampilkan ringkasan emosi, scene, pakaian, lokasi, handuk, dan climax."""

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
        world_state = orchestrator._load_or_init_world_state()
        role_id = user_state.active_role_id
        role_state = user_state.get_or_create_role_state(role_id)

        e = role_state.emotions
        r = role_state.relationship
        s = role_state.scene
        intimacy = role_state.intimacy_detail
        
        # ========== STATUS PAKAIAN ==========
        user_clothes = intimacy.user_clothing_removed
        role_clothes = intimacy.role_clothing_removed
        
        user_shirt = "âœ… LEPAS" if "baju" in user_clothes else "âŒ masih pake"
        user_pants = "âœ… LEPAS" if "celana" in user_clothes else "âŒ masih pake"
        user_underwear = "âœ… LEPAS" if "celana dalam" in user_clothes else "âŒ masih pake"
        
        role_shirt = "âœ… LEPAS" if ("baju" in role_clothes or "bra" in role_clothes) else "âŒ masih pake"
        role_pants = "âœ… LEPAS" if "celana" in role_clothes else "âŒ masih pake"
        role_underwear = "âœ… LEPAS" if "celana dalam" in role_clothes else "âŒ masih pake"
        
        # ========== STATUS LOKASI TERBARU ==========
        current_location = getattr(role_state, 'current_location_name', s.location or "belum ditentukan")
        location_private = "ðŸ”’ PRIVAT" if getattr(role_state, 'current_location_is_private', False) else "ðŸ‘€ PUBLIK/SEMI PRIVAT"
        household_summary = getattr(world_state, "current_household_note", "-")
        nova_home = "YA" if getattr(world_state, "nova_is_home", True) else "TIDAK"
        
        # ========== STATUS POSISI & INTIMASI ==========
        position = intimacy.position.value if intimacy.position else "belum ada"
        dominance = intimacy.dominance.value if intimacy.dominance else "netral"
        intensity = intimacy.intensity.value if intimacy.intensity else "foreplay"
        
        # ========== STATUS SENTUHAN & AKTIVITAS ==========
        last_touch = s.last_touch or "belum ada"
        last_action = intimacy.last_action or "belum ada"
        last_pleasure = intimacy.last_pleasure or "belum ada"
        
        # ========== STATUS HANDUK ==========
        handuk_tersedia = getattr(role_state, 'handuk_tersedia', False)
        handuk_status = "âœ… SEDANG DIPAKAI" if handuk_tersedia else "âŒ TIDAK ADA/TIDAK DIPAKAI"
        
        # ========== STATUS CLIMAX & EJAKULASI ==========
        role_climax_count = getattr(role_state, 'role_climax_count', 0)
        mas_has_climaxed = getattr(role_state, 'mas_has_climaxed', False)
        prefer_buang_di_dalam = getattr(role_state, 'prefer_buang_di_dalam', None)
        last_ejakulasi_inside = getattr(role_state, 'last_ejakulasi_inside', False)
        provider_service = role_state.session.provider_service_label or "-"
        provider_price = role_state.session.negotiated_price or "-"
        provider_deal = "YA" if role_state.session.deal_confirmed else "BELUM"
        
        role_wants_climax = getattr(role_state, 'role_wants_climax', False)
        mas_wants_climax = getattr(role_state, 'mas_wants_climax', False)
        role_holding_climax = getattr(role_state, 'role_holding_climax', False)
        mas_holding_climax = getattr(role_state, 'mas_holding_climax', False)
        pending_ejakulasi_question = getattr(role_state, 'pending_ejakulasi_question', False)
        aftercare_active = getattr(role_state, 'aftercare_active', False)
        
        # Status climax role
        if role_wants_climax:
            role_climax_status = "ðŸ”¥ MAU CLIMAX"
        elif role_holding_climax:
            role_climax_status = "â¸ï¸ MENAHAN CLIMAX"
        else:
            role_climax_status = "âŒ TIDAK"
        
        # Status climax Mas
        if mas_wants_climax:
            mas_climax_status = "ðŸ”¥ MAU CLIMAX"
        elif mas_holding_climax:
            mas_climax_status = "â¸ï¸ MENAHAN CLIMAX"
        elif mas_has_climaxed:
            mas_climax_status = "âœ… SUDAH CLIMAX"
        else:
            mas_climax_status = "âŒ BELUM"
        
        # Preferensi buang
        if prefer_buang_di_dalam is True:
            preferensi_buang = "DI DALAM"
        elif prefer_buang_di_dalam is False:
            preferensi_buang = "DI LUAR"
        else:
            preferensi_buang = "BELUM DITENTUKAN"
        
        # Ejakulasi terakhir
        if getattr(role_state, 'last_ejakulasi_timestamp', None) is None:
            last_ejakulasi_text = "BELUM PERNAH"
        else:
            last_ejakulasi_text = "DI DALAM" if last_ejakulasi_inside else "DI LUAR"
        
        # ========== BUILD PESAN STATUS ==========
        text_lines = [
            "ðŸŽ­ ROLE AKTIF: " + role_id,
            "",
            "â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”",
            "ðŸ“Š EMOSI & HUBUNGAN",
            "â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”",
            "â–ª Level hubungan: " + str(r.relationship_level) + "/12",
            "â–ª Love: " + str(e.love),
            "â–ª Longing (kangen): " + str(e.longing),
            "â–ª Jealousy (cemburu): " + str(e.jealousy),
            "â–ª Comfort (nyaman): " + str(e.comfort),
            "â–ª Intimacy intensity: " + str(e.intimacy_intensity) + "/12",
            "â–ª Mood: " + str(e.mood.value),
            "",
            "â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”",
            "ðŸ“ LOKASI & SCENE",
            "â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”",
            "â–ª Lokasi: " + current_location + " " + location_private,
            "â–ª Household: " + household_summary,
            "â–ª Nova di rumah: " + nova_home,
            "â–ª Posture: " + (s.posture or "-"),
            "â–ª Aktivitas: " + (s.activity or "-"),
            "â–ª Suasana: " + (s.ambience or "-"),
            "â–ª Waktu: " + (s.time_of_day.value if s.time_of_day else "-"),
            "â–ª Jarak fisik: " + (s.physical_distance or "-"),
            "â–ª Sentuhan terakhir: " + last_touch,
            "",
            "â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”",
            "ðŸ‘• STATUS PAKAIAN",
            "â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”",
            "â–ª MAS:",
            "   - Baju: " + user_shirt,
            "   - Celana: " + user_pants,
            "   - Celana dalam: " + user_underwear,
            "",
            "â–ª ROLE:",
            "   - Baju/Bra: " + role_shirt,
            "   - Celana: " + role_pants,
            "   - Celana dalam: " + role_underwear,
            "",
            "â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”",
            "ðŸ§º STATUS HANDUK",
            "â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”",
            "â–ª " + handuk_status,
            "",
            "â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”",
            "ðŸ›ï¸ ADEGAN INTIM",
            "â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”",
            "â–ª Posisi: " + position,
            "â–ª Dominasi: " + dominance,
            "â–ª Intensitas: " + intensity,
            "â–ª Aksi terakhir: " + last_action,
            "â–ª Perasaan terakhir: " + last_pleasure,
            "",
            "â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”",
            "ðŸ’¦ STATUS CLIMAX & EJAKULASI",
            "â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”",
            "â–ª Role climax count: " + str(role_climax_count) + "x",
            "â–ª Role climax status: " + role_climax_status,
            "â–ª Mas climax status: " + mas_climax_status,
            "â–ª Preferensi buang: " + preferensi_buang,
            "â–ª Provider service: " + str(provider_service),
            "â–ª Provider deal: " + provider_deal,
            "â–ª Harga deal: " + str(provider_price),
            "â–ª Ejakulasi terakhir: " + last_ejakulasi_text,
            "- Preferensi akhir pending: " + ("YA" if pending_ejakulasi_question else "TIDAK"),
            "- Aftercare aktif: " + ("YA" if aftercare_active else "TIDAK"),
        ]

        await chat.send_message("\n".join(text_lines))

    return _handler


# ==============================
# HANDLER /PAUSE dan /RESUME
# ==============================


def pause_handler(orchestrator: Orchestrator, admin_id: str):
    """/pause: pause sesi intens (tanpa reset state)."""

    @require_admin(admin_id)
    async def _handler(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        chat = update.effective_chat
        user = update.effective_user
        if chat is None or user is None:
            return

        user_state = orchestrator._load_or_init_user_state(str(user.id))  # type: ignore[attr-defined]
        user_state.global_session_mode = SessionMode.NORMAL
        orchestrator._save_all(user_state, orchestrator._load_or_init_world_state())  # type: ignore[attr-defined]

        await chat.send_message("â¸ï¸ Sesi dihentikan sementara. Ketik /resume untuk lanjut.")

    return _handler


def resume_handler(orchestrator: Orchestrator, admin_id: str):
    """/resume: lanjutkan sesi dari suasana terakhir."""

    @require_admin(admin_id)
    async def _handler(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        chat = update.effective_chat
        user = update.effective_user
        if chat is None or user is None:
            return

        user_state = orchestrator._load_or_init_user_state(str(user.id))  # type: ignore[attr-defined]
        user_state.global_session_mode = SessionMode.NORMAL
        orchestrator._save_all(user_state, orchestrator._load_or_init_world_state())  # type: ignore[attr-defined]

        await chat.send_message(
            "â–¶ï¸ Sesi dilanjutkan! Silakan lanjut ngobrol, role akan melanjutkan dari suasana terakhir."
        )

    return _handler


# ==============================
# HANDLER /FLASHBACK
# ==============================


def flashback_handler(orchestrator: Orchestrator, admin_id: str):
    """/flashback: minta role aktif cerita satu momen indah/khas."""

    @require_admin(admin_id)
    async def _handler(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        chat = update.effective_chat
        user = update.effective_user
        if chat is None or user is None:
            return

        inp = OrchestratorInput(
            user_id=str(user.id),
            text="/flashback",
            timestamp=time.time(),
            is_command=True,
            command_name="flashback",
        )
        out: OrchestratorOutput = orchestrator.handle_input(inp)
        await chat.send_message(out.reply_text)

    return _handler


# ==============================
# HANDLER PROVIDER: /nego, /deal, /mulai
# ==============================


def nego_handler(orchestrator: Orchestrator, admin_id: str):
    """/nego <harga>: nego harga untuk role provider."""

    @require_admin(admin_id)
    async def _handler(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        chat = update.effective_chat
        user = update.effective_user
        if chat is None or user is None:
            return

        text = update.effective_message.text or ""
        now_ts = time.time()

        inp = OrchestratorInput(
            user_id=str(user.id),
            text=text,
            timestamp=now_ts,
            is_command=True,
            command_name="nego",
        )
        out: OrchestratorOutput = orchestrator.handle_input(inp)
        await chat.send_message(out.reply_text)

    return _handler


def deal_handler(orchestrator: Orchestrator, admin_id: str):
    """/deal: konfirmasi deal setelah nego."""

    @require_admin(admin_id)
    async def _handler(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        chat = update.effective_chat
        user = update.effective_user
        if chat is None or user is None:
            return

        now_ts = time.time()

        inp = OrchestratorInput(
            user_id=str(user.id),
            text="/deal",
            timestamp=now_ts,
            is_command=True,
            command_name="deal",
        )
        out: OrchestratorOutput = orchestrator.handle_input(inp)
        await chat.send_message(out.reply_text)

    return _handler


def mulai_handler(orchestrator: Orchestrator, admin_id: str):
    """/mulai: mulai sesi provider setelah deal."""

    @require_admin(admin_id)
    async def _handler(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        chat = update.effective_chat
        user = update.effective_user
        if chat is None or user is None:
            return

        now_ts = time.time()

        inp = OrchestratorInput(
            user_id=str(user.id),
            text="/mulai",
            timestamp=now_ts,
            is_command=True,
            command_name="mulai",
        )
        out: OrchestratorOutput = orchestrator.handle_input(inp)
        await chat.send_message(out.reply_text)

    return _handler


# ==============================
# HANDLER PESAN BIASA
# ==============================


def message_handler(orchestrator: Orchestrator, admin_id: str):
    @require_admin(admin_id)
    async def _handler(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:

        if update.update_id in PROCESSED_UPDATES:
            return
        PROCESSED_UPDATES.add(update.update_id)
        if len(PROCESSED_UPDATES) > 1000:
            PROCESSED_UPDATES.clear()
        
        chat = update.effective_chat
        user = update.effective_user
        msg = update.effective_message
        if chat is None or user is None or msg is None:
            return

        text = msg.text or ""
        now_ts = time.time()

        inp = OrchestratorInput(
            user_id=str(user.id),
            text=text,
            timestamp=now_ts,
            is_command=text.startswith("/"),
            command_name=None,
        )

        out: OrchestratorOutput = orchestrator.handle_input(inp)
        await chat.send_message(out.reply_text)

    return _handler


