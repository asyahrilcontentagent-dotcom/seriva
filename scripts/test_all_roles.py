"""Quick test semua role SERIVA dengan DummyLLM.

Jalankan:

    python -m scripts.test_all_roles

Tujuan:
- Memastikan tidak ada role yang error saat dibangun prompt & dipanggil oleh Orchestrator.
- Tidak memanggil API LLM asli (pakai DummyLLMClient).

Output:
- Untuk setiap role_id, script akan mencetak:
  - Nama role
  - Sample reply dummy dari LLM
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from config.constants import ROLES
from core.orchestrator import (
    Orchestrator,
    OrchestratorInput,
    UserStateStore,
    WorldStateStore,
)
from storage.inmemory_store import (
    InMemoryUserStateStore,
    InMemoryWorldStateStore,
)
from memory.milestones import MilestoneStore


# ----------------------------------------
# Dummy LLM Client (tidak memanggil API)
# ----------------------------------------


@dataclass
class DummyLLMClient:
    """Client LLM palsu untuk cek wiring tanpa call ke API.

    Setiap role akan mendapatkan jawaban dummy yang menyebut namanya.
    """

    def generate_text(self, messages: list[dict], *, temperature: float | None = None, max_tokens: int | None = None, extra_params: dict | None = None) -> str:  # type: ignore[override]
        # Coba baca system prompt untuk menebak nama role
        system_prompt = ""
        for msg in messages:
            if msg.get("role") == "system":
                system_prompt = msg.get("content", "")
                break

        # Cari nama role dari system prompt (heuristik sederhana)
        role_name = "role"
        if "NOVA" in system_prompt or "Nova" in system_prompt:
            role_name = "Nova"
        elif "SISKA" in system_prompt or "Siska" in system_prompt:
            role_name = "Siska"
        elif "TASHA DIETHA" in system_prompt or "Dietha" in system_prompt:
            role_name = "Dietha"
        elif "Musdalifah" in system_prompt or "Ipeh" in system_prompt:
            role_name = "Ipeh"
        elif "Widya" in system_prompt:
            role_name = "Widya"
        elif "Davina" in system_prompt:
            role_name = "Davina"
        elif "Sallsa" in system_prompt:
            role_name = "Sallsa"
        elif "Aghnia" in system_prompt:
            role_name = "Aghnia"
        elif "Munira" in system_prompt:
            role_name = "Munira"

        return f"[DUMMY LLM] {role_name} merespon lembut: wiring untuk {role_name} OK."


# ----------------------------------------
# Adapter stores
# ----------------------------------------


class CheckUserStateStore(InMemoryUserStateStore, UserStateStore):
    """Adapter agar InMemoryUserStateStore cocok dengan tipe UserStateStore."""

    pass


class CheckWorldStateStore(InMemoryWorldStateStore, WorldStateStore):
    """Adapter agar InMemoryWorldStateStore cocok dengan tipe WorldStateStore."""

    pass


# ----------------------------------------
# Main test
# ----------------------------------------


def main() -> None:
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )
    logger = logging.getLogger("seriva.test_all_roles")

    logger.info("Mulai SERIVA test_all_roles dengan DummyLLM...")

    user_store = CheckUserStateStore()
    world_store = CheckWorldStateStore()
    milestone_store = MilestoneStore()

    dummy_llm = DummyLLMClient()

    orchestrator = Orchestrator(
        user_store=user_store,
        world_store=world_store,
        llm_client=dummy_llm,
        milestone_store=milestone_store,
    )

    test_user_id = "test_all_roles_user"

    print("=== SERIVA – Test Semua Role (DummyLLM) ===\n")

    for role_id, info in ROLES.items():
        # Set active_role_id manual di UserState
        user_state = user_store.load_user_state(test_user_id)
        if user_state is None:
            from seriva.core.state_models import UserState  # import lokal agar jelas

            user_state = UserState(user_id=test_user_id)
        user_state.active_role_id = role_id
        user_state.get_or_create_role_state(role_id)
        user_store.save_user_state(user_state)

        # Buat input dummy
        dummy_text = "(test) aku kangen kamu"  # teks yang aman & generik
        inp = OrchestratorInput(
            user_id=test_user_id,
            text=dummy_text,
            timestamp=0.0,
            is_command=False,
            command_name=None,
        )

        try:
            out = orchestrator.handle_input(inp)
            print(f"Role ID   : {role_id}")
            print(f"Nama      : {info.display_name} / alias {info.alias}")
            print(f"Kategori  : {info.category}")
            print(f"Reply     : {out.reply_text}")
            print("-" * 60)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Error saat mengetes role %s: %s", role_id, exc)
            print(f"Role ID   : {role_id}")
            print("STATUS    : ERROR (lihat log di atas)")
            print("-" * 60)

    print("\nTest semua role selesai.")


if __name__ == "__main__":
    main()
