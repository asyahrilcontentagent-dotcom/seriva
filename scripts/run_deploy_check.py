"""Pre-deploy sanity check untuk SERIVA.

Jalankan:

    python -m scripts.run_deploy_check

Tujuan:
- Pastikan semua modul utama bisa di-import tanpa error.
- Pastikan Orchestrator bisa di-inisialisasi dengan InMemory store dan
  MilestoneStore tanpa melempar exception.
- Lakukan satu "chat" dummy dengan Nova memakai DummyLLMClient yang tidak
  benar-benar memanggil API eksternal.

Jika semua langkah sukses, kamu akan melihat pesan "SEMUA OK" di akhir.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass


# ----------------------------------------
# Import core SERIVA
# ----------------------------------------

from config.constants import ROLES, ROLE_ID_NOVA  # noqa: F401
from core.state_models import UserState, WorldState  # noqa: F401
from core.emotion_engine import EmotionEngine  # noqa: F401
from core.scene_engine import SceneEngine  # noqa: F401
from core.world_engine import WorldEngine  # noqa: F401
from core.orchestrator import (
    Orchestrator,
    OrchestratorInput,
    UserStateStore,
    WorldStateStore,
)
from memory.milestones import MilestoneStore  # noqa: F401
from memory.message_history import MessageHistoryStore  # noqa: F401
from roles.role_registry import get_role  # noqa: F401
from storage.inmemory_store import (
    InMemoryUserStateStore,
    InMemoryWorldStateStore,
)


# ----------------------------------------
# Dummy LLM Client (tidak memanggil API)
# ----------------------------------------


@dataclass
class DummyLLMClient:
    """Client LLM palsu untuk cek wiring tanpa call ke API.

    Semua permintaan akan dijawab dengan pesan pendek statis.
    """

    def generate_text(self, messages: list[dict], *, temperature: float | None = None, max_tokens: int | None = None, extra_params: dict | None = None) -> str:  # type: ignore[override]
        # Ambil pesan user terakhir untuk sedikit konteks (opsional)
        last_user = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_user = msg.get("content", "")
                break

        # Jawaban dummy sederhana
        if last_user:
            return "[DUMMY LLM] Nova merespon lembut: Aku di sini kok, Mas. (cek wiring berhasil)"
        return "[DUMMY LLM] Cek LLM berhasil."


# ----------------------------------------
# InMemory store adapter untuk UserState / WorldState
# ----------------------------------------


class CheckUserStateStore(InMemoryUserStateStore, UserStateStore):
    """Adapter agar InMemoryUserStateStore cocok dengan tipe UserStateStore."""

    pass


class CheckWorldStateStore(InMemoryWorldStateStore, WorldStateStore):
    """Adapter agar InMemoryWorldStateStore cocok dengan tipe WorldStateStore."""

    pass


# ----------------------------------------
# Main check
# ----------------------------------------


def main() -> None:
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )
    logger = logging.getLogger("seriva.deploy_check")

    logger.info("Mulai SERIVA deploy check...")

    # 1. Inisialisasi stores & milestone store
    user_store = CheckUserStateStore()
    world_store = CheckWorldStateStore()
    milestone_store = MilestoneStore()

    # 2. Inisialisasi Orchestrator dengan DummyLLMClient
    dummy_llm = DummyLLMClient()

    orchestrator = Orchestrator(
        user_store=user_store,
        world_store=world_store,
        llm_client=dummy_llm,  # gunakan dummy
        milestone_store=milestone_store,
    )

    logger.info("Orchestrator berhasil diinisialisasi.")

    # 3. Lakukan satu percobaan chat dengan Nova
    test_user_id = "deploy_check_user"
    test_text = "aku kangen kamu"

    inp = OrchestratorInput(
        user_id=test_user_id,
        text=test_text,
        timestamp=0.0,
        is_command=False,
        command_name=None,
    )

    out = orchestrator.handle_input(inp)

    logger.info("OrchestratorOutput: role=%s, session_mode=%s", out.active_role_id, out.session_mode.value)
    logger.info("Sample reply: %s", out.reply_text)

    # 4. Cek bahwa role aktif Nova
    assert out.active_role_id == ROLE_ID_NOVA, "Role aktif seharusnya Nova untuk cek awal."

    print("SERIVA deploy check: SEMUA OK ✅")


if __name__ == "__main__":
    main()
