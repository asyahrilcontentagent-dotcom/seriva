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
            "- /nova → balik ke Nova\n"
            "- /role → lihat daftar role\n"
            "- /role <id> → pindah ke role tertentu\n"
            "- /pause → pause sesi intens saat ini\n"
            "- /resume → lanjutkan sesi yang di-pause\n"
            "- /batal, /end, /close → akhiri sesi khusus & balik ke chat biasa\n"
            "- /status → lihat ringkasan perasaan & adegan role aktif\n"
            "- /flashback → minta role cerita ulang momen indah kalian\n"
            "- /nego <harga>, /deal, /mulai → alur khusus untuk terapis & teman spesial"
        )

    return _handler

# ==============================
# HANDLER ROLE LIST & SWITCH
# ==============================


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
            "- /start -> mulai atau reset sapaan awal bot\n"
            "- /help -> tampilkan daftar command ini\n"
            "- /nova -> ngobrol dengan Nova (pasangan utama)\n"
            "- /role -> lihat daftar role yang tersedia\n"
            "- /role <id> -> pindah ke role tertentu (misal: /role teman_spesial_davina)\n"
            "- /pause -> pause sesi intens saat ini (roleplay/provider)\n"
            "- /resume -> lanjutkan sesi yang di-pause dari posisi terakhir\n"
            "- /cooldown -> turunkan state kembali ke fase dekat tanpa reset hubungan\n"
            "- /batal, /end, atau /close -> akhiri sesi khusus dan kembali ke mode normal\n"
            "- /offline -> paksa keluar dari mode chat/call/vps dan kembali ke tatap muka\n"
            "- /status -> lihat ringkasan perasaan dan adegan role aktif\n"
            "- /flashback -> minta role cerita ulang satu momen indah atau khas dengan Mas\n"
            "- /nego <harga> -> nego harga dengan terapis aktif\n"
            "- /nego <short|long> <harga> -> nego paket companion time teman spesial\n"
            "- /deal -> konfirmasi setelah nego\n"
            "- /venue <hotel|apartemen> -> pilih venue setelah /deal untuk role teman spesial\n"
            "- /mulai -> mulai sesi setelah /deal"
        )

    return _handler


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
        orchestrator.switch_active_role(user_state, ROLE_ID_NOVA)  # type: ignore[attr-defined]
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
        orchestrator.switch_active_role(user_state, role_id)  # type: ignore[attr-defined]
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


def cooldown_handler(orchestrator: Orchestrator, admin_id: str):
    """/cooldown: turunkan fase kembali ke dekat tanpa reset hubungan."""

    @require_admin(admin_id)
    async def _handler(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        chat = update.effective_chat
        user = update.effective_user
        if chat is None or user is None:
            return

        raw_text = update.effective_message.text if update.effective_message and update.effective_message.text else "/cooldown"
        inp = OrchestratorInput(
            user_id=str(user.id),
            text=raw_text,
            timestamp=time.time(),
            is_command=True,
            command_name="cooldown",
        )
        out: OrchestratorOutput = orchestrator.handle_input(inp)
        await chat.send_message(out.reply_text)

    return _handler

def offline_handler(orchestrator: Orchestrator, admin_id: str):
    """/offline: keluar dari mode chat/call/vps ke mode tatap muka."""
    
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
        orchestrator._clear_communication_mode(role_state)
        orchestrator._save_all(user_state, orchestrator._load_or_init_world_state())

        await chat.send_message(
            "Mode chat/telepon selesai. Sekarang kita anggap lagi tatap muka langsung, Mas~"
        )

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
        
        # Pakai display name yang sama dengan runtime prompt agar /status tidak beda sendiri.
        role_display = getattr(role_state, "role_display_name", "") or role_id
        
        # ========== STATUS PAKAIAN ==========
        user_clothes = intimacy.user_clothing_removed
        role_clothes = intimacy.role_clothing_removed
        
        def status_icon(condition):
            return "✅" if condition else "❌"
        
        def clothing_text(is_wearing):
            return "✅ Masih pakai" if is_wearing else "❌ Sudah lepas"

        user_shirt_off = "baju" in user_clothes
        user_pants_off = "celana" in user_clothes
        user_underwear_off = "celana dalam" in user_clothes
        
        role_shirt_off = ("baju" in role_clothes or "bra" in role_clothes)
        role_pants_off = "celana" in role_clothes
        role_underwear_off = "celana dalam" in role_clothes
        user_shirt_on = not user_shirt_off
        user_pants_on = not user_pants_off
        user_underwear_on = not user_underwear_off
        role_shirt_on = not role_shirt_off
        role_pants_on = not role_pants_off
        role_underwear_on = not role_underwear_off

        def safe_str(value, default="-"):
            return str(value) if value is not None and str(value).strip() else default
        
        # ========== STATUS LOKASI ==========
        current_location = getattr(role_state, 'current_location_name', "") or ""
        communication_mode = getattr(role_state, 'communication_mode', None)
        if communication_mode:
            current_location = safe_str(getattr(s, 'location', None), current_location or "belum ditentukan")
        elif current_location in {"", "belum ditentukan", "unknown"}:
            current_location = safe_str(getattr(s, 'location', None), "belum ditentukan")

        location_private = getattr(role_state, 'current_location_is_private', False)
        if current_location == safe_str(getattr(s, 'location', None), ""):
            lowered_location = current_location.lower()
            if any(token in lowered_location for token in ["kamar", "hotel", "apartemen", "tempat sendiri"]):
                location_private = True
        location_icon = "🔒 PRIVAT" if location_private else "👀 PUBLIK"
        nova_home = "✅ Ada" if getattr(world_state, "nova_is_home", True) else "❌ Tidak ada"
        
        nova_status = getattr(world_state, 'nova_last_known_status', "di rumah") or "di rumah"

        # ========== STATUS HANDUK ==========
        handuk_tersedia = getattr(role_state, 'handuk_tersedia', False)
        
        handuk_dikasih = getattr(role_state, 'handuk_dikasih', False)
        mas_handuk_tersedia = getattr(role_state, 'mas_handuk_tersedia', False)
        mas_handuk_dikasih = getattr(role_state, 'mas_handuk_dikasih', False)
        if handuk_tersedia:
            handuk_status = "✅ Ada / sedang dipakai"
        elif handuk_dikasih:
            handuk_status = "🟡 Ada / sudah dikasih"
        else:
            handuk_status = "❌ Tidak ada"

        if mas_handuk_tersedia:
            mas_handuk_status = "✅ Ada / sedang dipakai"
        elif mas_handuk_dikasih:
            mas_handuk_status = "🟡 Ada / sudah dikasih"
        else:
            mas_handuk_status = "❌ Tidak ada"

        # ========== STATUS CLIMAX ==========
        role_climax_count = getattr(role_state, 'role_climax_count', 0)
        mas_has_climaxed = getattr(role_state, 'mas_has_climaxed', False)
        prefer_buang = getattr(role_state, 'prefer_buang_di_dalam', None)
        
        if prefer_buang is True:
            prefer_text = "💦 DI DALAM"
        elif prefer_buang is False:
            prefer_text = "💦 DI LUAR"
        else:
            prefer_text = "❓ Belum ditentukan"
        
        # Mood emoji
        mood_emoji = {
            "neutral": "😐",
            "happy": "😊",
            "sad": "😢",
            "playful": "😏",
            "annoyed": "😤",
            "jealous": "😒",
            "tired": "😴",
            "tender": "🥰",
        }.get(e.mood.value, "😐")
        
        # Position emoji
        position_emoji = {
            "missionary": "🛌",
            "cowgirl": "🐎",
            "doggy": "🐕",
            "spoon": "🥄",
            "sitting": "🪑",
            "standing": "🧍",
            "edge": "🛏️",
            "car": "🚗",
        }.get(intimacy.position.value if intimacy.position else "", "💑")
        
        # ========== AMBIL NILAI DENGAN AMAN (CEGAH None) ==========
        relationship_level = getattr(r, 'relationship_level', 0)
        love = getattr(e, 'love', 0)
        longing = getattr(e, 'longing', 0)
        jealousy = getattr(e, 'jealousy', 0)
        comfort = getattr(e, 'comfort', 0)
        intimacy_intensity = getattr(e, 'intimacy_intensity', 0)
        mood_value = getattr(e.mood, 'value', 'neutral') if e.mood else 'neutral'
        
        posture = safe_str(getattr(s, 'posture', None))
        activity = safe_str(getattr(s, 'activity', None))
        ambience = safe_str(getattr(s, 'ambience', None))
        outfit = safe_str(getattr(s, 'outfit', None))
        time_of_day = getattr(s.time_of_day, 'value', '-') if s.time_of_day else '-'
        physical_distance = safe_str(getattr(s, 'physical_distance', None))
        last_touch = safe_str(getattr(s, 'last_touch', None))
        phase_value = safe_str(getattr(role_state.intimacy_phase, 'value', None) if getattr(role_state, 'intimacy_phase', None) else None)
        sequence_value = safe_str(getattr(role_state.current_sequence, 'value', None) if getattr(role_state, 'current_sequence', None) else None)
        unlock_score = getattr(role_state, 'high_intensity_unlock_score', 0)
        communication_mode = getattr(role_state, 'communication_mode', None)
        communication_turns = getattr(role_state, 'communication_mode_turns', 0)
        vcs_mode = getattr(role_state, 'vcs_mode', False)
        vcs_intensity = getattr(role_state, 'vcs_intensity', 0)

        communication_labels = {
            "chat": "CHAT HP",
            "call": "TELEPON",
            "vps": "VIDEO CALL",
        }
        communication_label = communication_labels.get(communication_mode, "TATAP MUKA LANGSUNG")
        communication_turns_text = f"{communication_turns} turn" if communication_mode else "0 turn"
        vcs_status = f"AKTIF ({vcs_intensity}%)" if vcs_mode else "NONAKTIF"
        
        # Emoji untuk mode komunikasi
        mode_emoji = {
            "chat": "💬",
            "call": "📞",
            "vps": "📹",
        }.get(communication_mode, "👤")
        
        position_value = safe_str(getattr(intimacy.position, 'value', None) if intimacy.position else None)
        dominance_value = safe_str(getattr(intimacy.dominance, 'value', None) if intimacy.dominance else None)
        intensity_value = safe_str(getattr(intimacy.intensity, 'value', None) if intimacy.intensity else None)
        last_action = safe_str(getattr(intimacy, 'last_action', None))
        last_pleasure = safe_str(getattr(intimacy, 'last_pleasure', None))
        
        # ========== BUILD PESAN (TANPA MARKDOWN) ==========
        text_lines = [
            f"🎭 {role_display} (Role aktif)",
            "",
            "📊 EMOSI & HUBUNGAN",
            f"   ❤️ Level hubungan: {relationship_level}/12",
            f"   💕 Love: {love}",
            f"   🥺 Kangen: {longing}",
            f"   😤 Cemburu: {jealousy}",
            f"   🛋️ Nyaman: {comfort}",
            f"   🔥 Intimacy: {intimacy_intensity}/12",
            f"   {mood_emoji} Mood: {mood_value}",
            "",
            "📍 LOKASI & SCENE",
            f"   🏠 Lokasi: {current_location} ({location_icon})",
            f"   🏡 Nova di rumah: {nova_home}",
            f"   Status Nova terakhir: {nova_status}",
            f"   Fase: {phase_value}",
            f"   Sequence: {sequence_value}",
            f"   🪑 Postur: {posture}",
            f"   🎬 Aktivitas: {activity}",
            f"   🌅 Suasana: {ambience}",
            f"   Outfit: {outfit}",
            f"   ⏰ Waktu: {time_of_day}",
            f"   📏 Jarak: {physical_distance}",
            f"   ✋ Sentuhan: {last_touch}",
            f"   Unlock vulgar: {unlock_score}/100",
            f"   {mode_emoji} Mode komunikasi: {communication_label}",
            f"   🔁 Durasi mode: {communication_turns_text}",
            f"   📹 VCS: {vcs_status}",
            "",
            "👕 STATUS PAKAIAN",
            "",
            "   👨 Mas:",
            f"      Baju: {clothing_text(user_shirt_on)}",
            f"      Celana: {clothing_text(user_pants_on)}",
            f"      Celana dalam: {clothing_text(user_underwear_on)}",
            "",
            f"   {role_display}:",
            f"      Baju/Bra: {clothing_text(role_shirt_on)}",
            f"      Celana: {clothing_text(role_pants_on)}",
            f"      Celana dalam: {clothing_text(role_underwear_on)}",
            "",
            "HANDUK",
            f"   Mas: {mas_handuk_status}",
            f"   Role: {handuk_status}",
            "",
            "",
            "🛏️ ADEGAN INTIM",
            f"   {position_emoji} Posisi: {position_value}",
            f"   👑 Dominasi: {dominance_value}",
            f"   🔥 Intensitas: {intensity_value}",
            f"   🎬 Aksi: {last_action}",
            f"   💭 Perasaan: {last_pleasure}",
            "",
            "💦 CLIMAX & EJAKULASI",
            f"   🔥 Role climax: {role_climax_count}x",
            f"   👨 Mas climax: {'✅ Sudah' if mas_has_climaxed else '❌ Belum'}",
            f"   📍 Preferensi buang: {prefer_text}",
        ]

        # Kirim tanpa parse_mode untuk menghindari error markdown
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

        await chat.send_message("⏸️ Sesi dihentikan sementara. Ketik /resume untuk lanjut.")

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
        role_state = user_state.get_or_create_role_state(user_state.active_role_id)
        orchestrator._sync_global_session_mode(user_state)  # type: ignore[attr-defined]
        orchestrator._save_all(user_state, orchestrator._load_or_init_world_state())  # type: ignore[attr-defined]

        await chat.send_message(
            "▶️ Sesi dilanjutkan! Silakan lanjut ngobrol, role akan melanjutkan dari suasana terakhir."
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
# HANDLER PROVIDER: /nego, /deal, /venue, /mulai
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


def venue_handler(orchestrator: Orchestrator, admin_id: str):
    """/venue <hotel|apartemen>: pilih venue untuk provider teman spesial."""

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
        venue_arg = args[0].strip() if args else ""
        now_ts = time.time()

        inp = OrchestratorInput(
            user_id=str(user.id),
            text=update.effective_message.text or "/venue",
            timestamp=now_ts,
            is_command=True,
            command_name="venue",
            command_arg=venue_arg,
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
