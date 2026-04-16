from __future__ import annotations

from core.behavior_guard import BehaviorGuard
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
        return messages

    def finalize_reply(
        self,
        role_state: RoleState,
        user_text: str,
        reply_text: str,
    ) -> str:
        guard_result = self.behavior_guard.validate(role_state, user_text, reply_text)
        return guard_result.reply_text

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
