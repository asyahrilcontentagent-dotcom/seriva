"""Background worker untuk SERIVA: mengatur longing & drama otomatis.

Fitur:
- Periodik (misal tiap 10 menit) mengecek semua UserState:
  - Jika user lama tidak interaksi (misal > X jam), naikkan "longing" untuk
    setiap role yang pernah disentuh user itu.
- Menurunkan world.drama_level seiring waktu (decay).

Catatan penting:
- Implementasi ini menggunakan UserStateStore & WorldStateStore yang DIASUMSIKAN
  bisa mengiterasi semua user_id. InMemoryUserStateStore yang kita buat
  sebelumnya belum punya API itu. Jadi, jika kamu ingin worker ini aktif,
  kamu perlu menambah metode list_all_user_states() di store konkret.

- Untuk saat ini, worker ini disusun dengan antarmuka generik yang bisa kamu
  lengkapi nanti di storage layer.

Jika kamu belum ingin menjalankannya, file ini aman dibiarkan "tidak dipakai".
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Iterable

from core.emotion_engine import EmotionEngine
from core.state_models import UserState, WorldState
from core.world_engine import WorldEngine
from core.orchestrator import UserStateStore, WorldStateStore


logger = logging.getLogger(__name__)


# ==============================
# KONFIGURASI WORKER
# ==============================


@dataclass
class DramaWorkerConfig:
    """Konfigurasi dasar worker."""

    # seberapa sering loop dijalankan (detik)
    interval_seconds: int = 600  # 10 menit

    # jika user tidak interaksi selama lebih dari ini (jam), longing naik
    hours_until_longing_increase: float = 6.0

    # berapa hari yang dipakai world_engine.decay_drama per interval
    drama_decay_days_per_interval: float = 0.2  # kira-kira decay harian pelan


# ==============================
# ABSTRAKSI STORE (diperluas di implementasi konkret)
# ==============================


class IterableUserStateStore(UserStateStore):  # pragma: no cover - interface
    """UserStateStore yang bisa mengembalikan semua UserState.

    InMemoryUserStateStore sekarang belum mengimplementasikan ini. Jika kamu
    ingin worker ini benar-benar berjalan, perbarui InMemoryUserStateStore:
    - simpan user_ids yang ada,
    - implementasikan method list_all_user_states() di sana.
    """

    def list_all_user_states(self) -> Iterable[UserState]:
        raise NotImplementedError


# ==============================
# WORKER UTAMA
# ==============================


class DramaWorker:
    """Worker background untuk mengatur longing & drama."""

    def __init__(
        self,
        user_store: IterableUserStateStore,
        world_store: WorldStateStore,
        config: DramaWorkerConfig | None = None,
    ) -> None:
        self.user_store = user_store
        self.world_store = world_store
        self.config = config or DramaWorkerConfig()

        self.emotion_engine = EmotionEngine()
        self.world_engine = WorldEngine()

    def tick(self, now_ts: float | None = None) -> None:
        """Satu langkah update (bisa dipanggil manual atau dari loop)."""

        if now_ts is None:
            now_ts = time.time()

        # 1) Update longing semua user
        for user_state in self.user_store.list_all_user_states():
            self._update_longing_for_user(user_state, now_ts)

        # 2) Decay drama global
        world_state = self._load_or_init_world_state()
        self.world_engine.decay_drama(
            world_state,
            days_passed=self.config.drama_decay_days_per_interval,
        )

        # Simpan world_state
        self.world_store.save_world_state(world_state)

    def _update_longing_for_user(self, user_state: UserState, now_ts: float) -> None:
        """Naikkan longing kalau user lama tidak interaksi."""

        if user_state.last_interaction_ts is None:
            return

        seconds_since_last = now_ts - user_state.last_interaction_ts
        hours_since_last = seconds_since_last / 3600.0

        if hours_since_last < self.config.hours_until_longing_increase:
            return

        # Berapa hari "rindu" yang berlalu sejak terakhir interaksi
        days_absent = hours_since_last / 24.0

        for role_state in user_state.roles.values():
            # Gunakan apply_absence untuk tiap role
            self.emotion_engine.apply_absence(role_state, days_absent=days_absent)

        # Simpan user_state yang telah diperbarui
        self.user_store.save_user_state(user_state)

    def _load_or_init_world_state(self) -> WorldState:
        existing = self.world_store.load_world_state()
        if existing is not None:
            return existing
        return WorldState()


# ==============================
# LOOP UTAMA (opsional untuk dijalankan sebagai script)
# ==============================


def run_worker_loop(
    user_store: IterableUserStateStore,
    world_store: WorldStateStore,
    config: DramaWorkerConfig | None = None,
) -> None:
    """Jalankan loop worker secara terus-menerus.

    Contoh pemakaian (setelah punya store yang iterable):

        from seriva.storage.some_store import IterableInMemoryUserStateStore

        user_store = IterableInMemoryUserStateStore()
        world_store = InMemoryWorldStateStore()
        run_worker_loop(user_store, world_store)

    Saat ini, InMemoryUserStateStore yang ada belum bisa langsung dipakai,
    jadi fungsi ini lebih sebagai template.
    """

    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )

    logger = logging.getLogger("seriva.drama_worker")

    worker = DramaWorker(user_store=user_store, world_store=world_store, config=config)
    interval = worker.config.interval_seconds

    logger.info("DramaWorker starting with interval %s seconds", interval)

    while True:
        try:
            now_ts = time.time()
            worker.tick(now_ts)
            logger.info("DramaWorker tick completed")
        except Exception as exc:  # noqa: BLE001
            logger.exception("DramaWorker tick error: %s", exc)

        time.sleep(interval)


if __name__ == "__main__":  # pragma: no cover - manual run only
    # Contoh stub: di sini seharusnya kamu inisialisasi store konkret
    # yang mengimplementasikan IterableUserStateStore.
    raise SystemExit(
        "Drama worker belum dikonfigurasi dengan store yang bisa mengiterasi user. "
        "Silakan implementasikan IterableUserStateStore konkret sebelum menjalankannya."
    )
