"""In-memory storage untuk SERIVA.

Dipakai untuk development/testing tanpa database.

- Menyimpan UserState dan WorldState di dictionary Python.
- Tidak persisten (kalau process mati, data hilang).
"""

from __future__ import annotations

from threading import RLock
from typing import Dict, Optional
import time
import logging

from core.state_models import UserState, WorldState

# Import type hints saja untuk hindari circular import
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.orchestrator import UserStateStore, WorldStateStore

logger = logging.getLogger(__name__)


class InMemoryUserStateStore:
    """Implementasi UserStateStore di memori (thread-safe sederhana)."""
    
    # Tambahan: cleanup untuk user inactive
    INACTIVE_DAYS = 7  # hapus user setelah 7 hari tidak interaksi

    def __init__(self) -> None:
        self._lock = RLock()
        self._states: Dict[str, UserState] = {}
        self._last_access: Dict[str, float] = {}  # track last access

    def load_user_state(self, user_id: str):
        """Load user state dari memory."""
        with self._lock:
            # Update last access time
            self._last_access[user_id] = time.time()
            return self._states.get(user_id)

    def save_user_state(self, state: UserState) -> None:
        """Save user state ke memory."""
        if not isinstance(state, UserState):
            raise TypeError(f"Expected UserState, got {type(state)}")
        
        with self._lock:
            self._states[state.user_id] = state
            self._last_access[state.user_id] = time.time()
            logger.debug(f"Saved user state for {state.user_id}")

    def cleanup_inactive_users(self) -> int:
        """Hapus user yang sudah tidak aktif.
        
        Returns:
            Jumlah user yang dihapus
        """
        now = time.time()
        cutoff = now - (self.INACTIVE_DAYS * 24 * 3600)
        
        with self._lock:
            inactive = [
                uid for uid, last_access in self._last_access.items()
                if last_access < cutoff
            ]
            for uid in inactive:
                self._states.pop(uid, None)
                self._last_access.pop(uid, None)
            
        if inactive:
            logger.info(f"Cleaned up {len(inactive)} inactive users")
        return len(inactive)

    def get_active_users_count(self) -> int:
        """Dapatkan jumlah user aktif."""
        with self._lock:
            return len(self._states)


class InMemoryWorldStateStore:
    """Implementasi WorldStateStore di memori (global tunggal)."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._state: Optional[WorldState] = None

    def load_world_state(self):
        """Load world state dari memory."""
        with self._lock:
            return self._state

    def save_world_state(self, state: WorldState) -> None:
        """Save world state ke memory."""
        if not isinstance(state, WorldState):
            raise TypeError(f"Expected WorldState, got {type(state)}")
        
        with self._lock:
            self._state = state
            logger.debug("Saved world state")

    def reset(self) -> None:
        """Reset world state ke default."""
        with self._lock:
            self._state = WorldState()
            logger.info("Reset world state")
