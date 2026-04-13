"""Quick manual test untuk Nova di SERIVA.

Jalankan dengan:

    python -m scripts.test_nova

Pastikan environment LLM sudah di-set:
- LLM_API_KEY
- LLM_BASE_URL
- LLM_MODEL
"""

from __future__ import annotations

import time

from core.llm_client import LLMClient
from core.orchestrator import Orchestrator, OrchestratorInput
from storage.inmemory_store import (
    InMemoryUserStateStore,
    InMemoryWorldStateStore,
)


def main() -> None:
    user_store = InMemoryUserStateStore()
    world_store = InMemoryWorldStateStore()
    llm = LLMClient()

    orchestrator = Orchestrator(
        user_store=user_store,
        world_store=world_store,
        llm_client=llm,
    )

    user_id = "test_user_1"

    print("=== SERIVA / Nova quick test ===")
    print("Ketik pesan untuk Nova. Ketik 'exit' untuk keluar.\n")

    while True:
        try:
            text = input("Mas: ")
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar.")
            break

        if text.strip().lower() in {"exit", "quit"}:
            print("Keluar.")
            break

        now_ts = time.time()

        inp = OrchestratorInput(
            user_id=user_id,
            text=text,
            timestamp=now_ts,
            is_command=text.startswith("/"),
        )

        out = orchestrator.handle_input(inp)

        print(f"Nova: {out.reply_text}\n")


if __name__ == "__main__":
    main()
