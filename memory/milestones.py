"""Milestone memory management for SERIVA.

Menyimpan dan mengambil "kenangan penting" (milestone) per user-role,
untuk dipakai saat /flashback.

Contoh milestone:
- pertama kali Mas bilang sayang
- pertama kali pelukan (digambarkan halus)
- malam tertentu yang sangat berkesan

Saat ini implementasi di memori (in-memory). Kemudian bisa dipindah ke
storage persisten (SQLite) jika diperlukan.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Dict, List, Optional


@dataclass
class Milestone:
    """Satu kenangan penting antara user dan role."""

    user_id: str
    role_id: str
    timestamp: float  # unix timestamp
    label: str        # kategori bebas, misal: "first_confession", "special_night"
    description: str  # narasi singkat, aman & non-vulgar


class MilestoneStore:
    """Menyimpan milestone di memori.

    Struktur: dict[(user_id, role_id)] -> list[Milestone]
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._data: Dict[tuple[str, str], List[Milestone]] = {}

    # ----------------------------------------
    # API publik
    # ----------------------------------------

    def add_milestone(
        self,
        user_id: str,
        role_id: str,
        timestamp: float,
        label: str,
        description: str,
        max_per_pair: int = 20,
    ) -> None:
        """Tambahkan satu milestone untuk (user, role).

        max_per_pair membatasi panjang list agar tidak membengkak.
        """

        key = (user_id, role_id)
        m = Milestone(
            user_id=user_id,
            role_id=role_id,
            timestamp=timestamp,
            label=label,
            description=description,
        )

        with self._lock:
            lst = self._data.setdefault(key, [])
            lst.append(m)
            # Sort by time ascending lalu jaga panjang
            lst.sort(key=lambda x: x.timestamp)
            if len(lst) > max_per_pair:
                # buang yang paling lama di awal
                del lst[0 : len(lst) - max_per_pair]

    def get_recent_milestones(
        self,
        user_id: str,
        role_id: str,
        limit: int = 5,
    ) -> List[Milestone]:
        """Ambil beberapa milestone terbaru untuk (user, role)."""

        key = (user_id, role_id)
        with self._lock:
            lst = self._data.get(key, [])
            if not lst:
                return []
            return lst[-limit:]

    def get_best_flashback_candidate(
        self,
        user_id: str,
        role_id: str,
    ) -> Optional[Milestone]:
        """Ambil satu milestone terbaik untuk /flashback.

        Strategi sederhana:
        - Kalau ada milestone dengan label "special_night" atau "first_confession",
          prioritaskan itu.
        - Kalau tidak ada, ambil milestone terbaru saja.
        """

        key = (user_id, role_id)
        with self._lock:
            lst = self._data.get(key, [])
            if not lst:
                return None

            # Cari label yang lebih "berat" dulu
            priority_labels = ["special_night", "first_confession", "first_hug"]
            for label in priority_labels:
                candidates = [m for m in lst if m.label == label]
                if candidates:
                    # ambil yang terbaru di label itu
                    candidates.sort(key=lambda x: x.timestamp)
                    return candidates[-1]

            # fallback: milestone terbaru apa pun
            lst.sort(key=lambda x: x.timestamp)
            return lst[-1]

    def reset_role_milestones(self, user_id: str, role_id: str) -> None:
        """Hapus semua milestone untuk satu pasangan user-role."""

        key = (user_id, role_id)
        with self._lock:
            self._data.pop(key, None)
