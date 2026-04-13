"""In-memory storage untuk SERIVA.

Dipakai untuk development/testing tanpa database.

- Menyimpan UserState dan WorldState di dictionary Python.
- Tidak persisten (kalau process mati, data hilang).
"""

from __future__ import annotations

from threading import RLock
from typing import Dict, Optional

from core.state_models import UserState, WorldState
from core.orchestrator import UserStateStore, WorldStateStore


class InMemoryUserStateStore(UserStateStore):
    """Implementasi UserStateStore di memori (thread-safe sederhana)."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._states: Dict[str, UserState] = {}

    def load_user_state(self, user_id: str) -> Optional[UserState]:
        with self._lock:
            return self._states.get(user_id)

    def save_user_state(self, state: UserState) -> None:
        with self._lock:
            self._states[state.user_id] = state


class InMemoryWorldStateStore(WorldStateStore):
    """Implementasi WorldStateStore di memori (global tunggal)."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._state: Optional[WorldState] = None

    def load_world_state(self) -> Optional[WorldState]:
        with self._lock:
            return self._state

    def save_world_state(self, state: WorldState) -> None:
        with self._lock:
            self._state = state
