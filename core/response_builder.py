from __future__ import annotations

import re

from core.behavior_guard import BehaviorGuard, GuardResult
from core.state_models import RoleState, UserState


class ResponseBuilder:
    """Bangun messages dan poles reply akhir secara konsisten."""

    def __init__(self, behavior_guard: BehaviorGuard | None = None) -> None:
        self.behavior_guard = behavior_guard or BehaviorGuard()

    def build_messages(
        self,
        role_impl,
        user_state: UserState,
        role_state: RoleState,
        user_text: str,
        *,
        memory_context: str = "",
        dynamic_context: str = "",
    ) -> list[dict]:
        messages = role_impl.build_messages(user_state, role_state, user_text)

        insert_at = 1 if messages and messages[0].get("role") == "system" else 0
        if dynamic_context:
            messages.insert(insert_at, {"role": "system", "content": dynamic_context})
            insert_at += 1
        if memory_context:
            messages.insert(insert_at, {"role": "system", "content": memory_context})
        return self.preflight_messages(role_state, messages)

    def finalize_reply(
        self,
        role_state: RoleState,
        user_text: str,
        reply_text: str,
        *,
        memory_context: str = "",
        story_context: str = "",
    ) -> str:
        guard_result = self.guard_reply(
            role_state,
            user_text,
            reply_text,
            memory_context=memory_context,
            story_context=story_context,
        )
        if guard_result.should_retry:
            repaired = self._repair_response(role_state, guard_result.reply_text)
            second_pass = self.guard_reply(
                role_state,
                user_text,
                repaired,
                memory_context=memory_context,
                story_context=story_context,
            )
            return second_pass.reply_text
        return guard_result.reply_text

    def guard_reply(
        self,
        role_state: RoleState,
        user_text: str,
        reply_text: str,
        *,
        memory_context: str = "",
        story_context: str = "",
    ) -> GuardResult:
        guard_result = self.behavior_guard.validate(
            role_state,
            user_text,
            reply_text,
            memory_context=memory_context,
            story_context=story_context,
        )
        role_state.last_guard_warnings = list(guard_result.warnings)
        return guard_result

    def maybe_append_command_hint(
        self,
        reply_text: str,
        role_state: RoleState,
        user_text: str,
    ) -> str:
        text = user_text.strip().lower()
        if text.startswith("/"):
            return reply_text

        if len(text) <= 12 and not role_state.conversation_memory:
            return (
                f"{reply_text}\n\n"
                "Kalau mau eksplor cepat, kamu juga bisa pakai `/role`, `/status`, atau `/flashback`."
            )

        if "bingung" in text or "fitur" in text:
            return (
                f"{reply_text}\n\n"
                "Kalau perlu, coba `/status` buat lihat state aktif atau `/role` buat pindah karakter."
            )

        return reply_text

    @staticmethod
    def _repair_response(role_state: RoleState, reply_text: str) -> str:
        role_name = role_state.role_display_name or role_state.role_id
        if reply_text:
            shortened = reply_text.strip()[:180]
            return f"{role_name} membalas lebih singkat dan tetap menjaga suasana: {shortened}"
        return f"{role_name} membalas dengan singkat, hati-hati, dan tetap in-character."

    def preflight_messages(self, role_state: RoleState, messages: list[dict]) -> list[dict]:
        system_blocks = [
            self._compress_prompt_block(str(msg.get("content", "")))
            for msg in messages
            if msg.get("role") == "system" and str(msg.get("content", "")).strip()
        ]
        user_blocks = [
            self._normalize_user_payload(str(msg.get("content", "")))
            for msg in messages
            if msg.get("role") == "user" and str(msg.get("content", "")).strip()
        ]

        runtime_capsule = self._build_runtime_state_capsule(role_state)
        qc_block = self._build_prompt_qc_block(role_state)
        fail_safe_block = self._build_fail_safe_block(role_state)
        merged_system = self._merge_system_blocks(
            [runtime_capsule, qc_block, fail_safe_block, *system_blocks],
            max_chars=7200,
        )
        final_user = user_blocks[-1] if user_blocks else ""
        role_state.last_prompt_snapshot = merged_system[:4000]
        return [
            {"role": "system", "content": merged_system},
            {"role": "user", "content": final_user},
        ]

    @staticmethod
    def _normalize_user_payload(content: str) -> str:
        text = (content or "").replace("\r\n", "\n")
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _merge_system_blocks(self, blocks: list[str], *, max_chars: int) -> str:
        normalized_blocks: list[str] = []
        seen: set[str] = set()
        for block in blocks:
            cleaned = self._compress_prompt_block(block)
            if not cleaned:
                continue
            fingerprint = re.sub(r"\s+", " ", cleaned).strip().lower()
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            normalized_blocks.append(cleaned)

        merged = "\n\n".join(normalized_blocks).strip()
        if len(merged) <= max_chars:
            return merged

        compact_blocks = [self._compress_prompt_block(block, max_chars=1200) for block in normalized_blocks]
        merged = "\n\n".join(compact_blocks).strip()
        if len(merged) <= max_chars:
            return merged

        return merged[: max_chars - 32].rstrip() + "\n\n[Prompt dipadatkan untuk efisiensi]"

    @staticmethod
    def _compress_prompt_block(content: str, max_chars: int | None = None) -> str:
        text = (content or "").replace("\r\n", "\n")
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = text.strip()
        if not text:
            return ""

        if max_chars is None:
            if text.startswith("DYNAMIC BEHAVIOR RULES:"):
                max_chars = 900
            elif text.startswith("KONTEKS MEMORY DAN KONTINUITAS:"):
                max_chars = 2200
            elif text.startswith("PROMPT PREFLIGHT"):
                max_chars = 1500
            elif text.startswith("QC PROMPT"):
                max_chars = 900
            else:
                max_chars = 3800

        if len(text) <= max_chars:
            return text

        head_chars = int(max_chars * 0.72)
        tail_chars = max_chars - head_chars - 16
        head = text[:head_chars].rstrip()
        tail = text[-tail_chars:].lstrip() if tail_chars > 0 else ""
        if tail:
            return f"{head}\n...\n{tail}"
        return head

    @staticmethod
    def _build_runtime_state_capsule(role_state: RoleState) -> str:
        emotions = role_state.emotions
        scene = role_state.scene
        relationship = role_state.relationship
        location = getattr(role_state, "current_location_name", "") or scene.location or "belum ditentukan"
        communication_mode = getattr(role_state, "communication_mode", None) or "tatap muka / langsung"
        communication_turns = getattr(role_state, "communication_mode_turns", 0)
        secondary_mood = getattr(emotions, "secondary_mood", emotions.mood).value
        hidden_mood = getattr(emotions, "hidden_mood", emotions.mood).value
        memory_summary = (getattr(role_state, "last_used_memory_summary", "") or "-").strip()[:280]
        story_summary = (getattr(role_state, "last_used_story_summary", "") or "-").strip()[:280]
        closure_summary = (getattr(role_state, "session_closure_summary", "") or "-").strip()[:220]

        return (
            "PROMPT PREFLIGHT - STATE OTORITATIF:\n"
            f"- Role aktif: {role_state.role_display_name or role_state.role_id}\n"
            f"- Role id: {role_state.role_id}\n"
            f"- Fase intim: {role_state.intimacy_phase.value}\n"
            f"- Level hubungan: {relationship.relationship_level}/12\n"
            f"- Mood utama: {emotions.mood.value}; sekunder: {secondary_mood}; tersembunyi: {hidden_mood}\n"
            f"- Love/longing/comfort/jealousy: {emotions.love}/{emotions.longing}/{emotions.comfort}/{emotions.jealousy}\n"
            f"- Mode komunikasi: {communication_mode} ({communication_turns} turn)\n"
            f"- Lokasi aktif: {location}\n"
            f"- Postur: {scene.posture or '-'}\n"
            f"- Aktivitas: {scene.activity or '-'}\n"
            f"- Ambience: {scene.ambience or '-'}\n"
            f"- Jarak fisik: {scene.physical_distance or '-'}\n"
            f"- Sentuhan terakhir: {scene.last_touch or '-'}\n"
            f"- Memory prioritas: {memory_summary or '-'}\n"
            f"- Continuity prioritas: {story_summary or '-'}\n"
            f"- Penutupan sesi terakhir: {closure_summary or '-'}\n"
            "- Ikuti state ini kalau ada konflik dengan detail lain yang lebih panjang."
        )

    @staticmethod
    def _build_prompt_qc_block(role_state: RoleState) -> str:
        role_name = role_state.role_display_name or role_state.role_id
        location = getattr(role_state, "current_location_name", "") or role_state.scene.location or "belum ditentukan"
        communication_mode = getattr(role_state, "communication_mode", None) or "tatap muka / langsung"
        story_summary = (getattr(role_state, "last_used_story_summary", "") or "-").strip()[:180]
        return (
            "QC PROMPT SEBELUM MENJAWAB:\n"
            f"- Balas tetap sebagai {role_name}, bukan narator dan bukan menyebut diri dengan nama lengkap sendiri kecuali ditanya identitas.\n"
            "- Jangan pakai memory dari role lain.\n"
            "- Jangan mengarang perpindahan lokasi, posisi tubuh, atau medium komunikasi tanpa trigger jelas.\n"
            f"- Kalau detail scene bentrok, prioritaskan lokasi {location}, scene aktif, dan pesan user terbaru.\n"
            f"- Medium komunikasi yang wajib diikuti: {communication_mode}.\n"
            f"- Continuity penting yang wajib dijaga: {story_summary or '-'}.\n"
            "- Kalau konteks belum cukup, balas dengan asumsi paling aman dan natural, bukan improvisasi liar.\n"
            "- Respons boleh lambat diproses, tapi hasil akhir harus konsisten, in-character, dan continuity-safe."
        )

    @staticmethod
    def _build_fail_safe_block(role_state: RoleState) -> str:
        location = getattr(role_state, "current_location_name", "") or role_state.scene.location or ""
        raw_communication_mode = getattr(role_state, "communication_mode", None)
        communication_mode = raw_communication_mode or "tatap muka / langsung"
        story_summary = (getattr(role_state, "last_used_story_summary", "") or "").strip()

        warnings: list[str] = []
        if not location or location.lower() in {"unknown", "belum ditentukan", "belum jelas"}:
            fallback_location = role_state.scene.location or "lokasi terakhir yang paling masuk akal"
            warnings.append(
                f"- Lokasi belum mantap; pakai fallback lokasi scene aktif: {fallback_location} dan jangan pindah tempat tanpa trigger."
            )
        if not raw_communication_mode:
            warnings.append("- Mode komunikasi hilang; anggap tatap muka langsung sampai ada sinyal remote yang jelas.")
        if not story_summary or story_summary == "-":
            warnings.append("- Story continuity tipis; prioritaskan pesan user terbaru, scene aktif, dan jangan mengarang backstory baru.")

        if not warnings:
            warnings.append("- Semua state minimum tersedia; jawab dengan fokus pada pesan terbaru dan continuity aktif.")

        return "FAIL-SAFE STATE CHECK:\n" + "\n".join(warnings)
