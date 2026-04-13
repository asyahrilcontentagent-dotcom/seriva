"""Message history management for SERIVA.

Menyimpan ringkasan pesan terbaru per user-role.

Tujuan:
- Menyimpan beberapa pesan terakhir yang relevan (teks pendek),
  bukan full transcript, agar hemat memori.
- Bisa dipakai nanti untuk:
  - memberi konteks tambahan ke prompt (kalau mau),
  - mendeteksi momen penting (misalnya first_confession) untuk milestones.

Saat ini implementasi di memori (in-memory), mirip dengan MilestoneStore.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Dict, List, Literal


MessageRole = Literal["user", "assistant"]


@dataclass
class MessageSnippet:
    """Satu potongan pesan yang disimpan.

    Ini bukan full pesan Telegram, hanya teks pendek + info dasar.
    """

    user_id: str
    role_id: str
    from_who: MessageRole  # "user" atau "assistant"
    timestamp: float
    content: str


class MessageHistoryStore:
    """In-memory store untuk message history SERIVA.

    Struktur data:
    - key: (user_id, role_id)
    - value: list[MessageSnippet] (urut waktu naik)
    """

    def __init__(self, max_per_pair: int = 100) -> None:
        self._lock = RLock()
        self._data: Dict[tuple[str, str], List[MessageSnippet]] = {}
        self.max_per_pair = max_per_pair

    # ----------------------------------------
    # API publik
    # ----------------------------------------

    def add_message(
        self,
        user_id: str,
        role_id: str,
        from_who: MessageRole,
        timestamp: float,
        content: str,
    ) -> None:
        """Tambahkan pesan ke history.

        - content boleh teks penuh, tapi disarankan dipotong manual di pemanggil
          kalau sangat panjang.
        """

        key = (user_id, role_id)
        snippet = MessageSnippet(
            user_id=user_id,
            role_id=role_id,
            from_who=from_who,
            timestamp=timestamp,
            content=content,
        )

        with self._lock:
            lst = self._data.setdefault(key, [])
            lst.append(snippet)
            # Jaga panjang maksimum
            if len(lst) > self.max_per_pair:
                del lst[0 : len(lst) - self.max_per_pair]

    def get_recent_messages(
        self,
        user_id: str,
        role_id: str,
        limit: int = 20,
    ) -> List[MessageSnippet]:
        """Ambil beberapa pesan terbaru untuk (user, role)."""

        key = (user_id, role_id)
        with self._lock:
            lst = self._data.get(key, [])
            if not lst:
                return []
            return lst[-limit:]

    def get_recent_user_messages(
        self,
        user_id: str,
        role_id: str,
        limit: int = 10,
    ) -> List[MessageSnippet]:
        """Ambil beberapa pesan terbaru yang dikirim oleh user ke role ini."""

        all_msgs = self.get_recent_messages(user_id, role_id, limit=limit * 2)
        user_msgs = [m for m in all_msgs if m.from_who == "user"]
        return user_msgs[-limit:]

    def get_recent_assistant_messages(
        self,
        user_id: str,
        role_id: str,
        limit: int = 10,
    ) -> List[MessageSnippet]:
        """Ambil beberapa pesan terbaru yang dikirim role (assistant) ke user."""

        all_msgs = self.get_recent_messages(user_id, role_id, limit=limit * 2)
        asst_msgs = [m for m in all_msgs if m.from_who == "assistant"]
        return asst_msgs[-limit:]

    def reset_role_history(self, user_id: str, role_id: str) -> None:
        """Hapus semua history untuk satu pasangan user-role."""

        key = (user_id, role_id)
        with self._lock:
            self._data.pop(key, None)
