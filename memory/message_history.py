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
import re


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

    def get_ranked_messages(
        self,
        user_id: str,
        role_id: str,
        limit: int = 6,
        query_text: str = "",
    ) -> List[MessageSnippet]:
        """Ambil pesan paling relevan berdasarkan recency + bobot emosional + keyword."""

        recent = self.get_recent_messages(user_id, role_id, limit=max(limit * 4, 20))
        scored = sorted(
            recent,
            key=lambda msg: self._score_message(msg, query_text=query_text),
            reverse=True,
        )
        return scored[:limit]

    def summarize_recent_messages(
        self,
        user_id: str,
        role_id: str,
        limit: int = 6,
        query_text: str = "",
    ) -> str:
        ranked = self.get_ranked_messages(user_id, role_id, limit=limit, query_text=query_text)
        if not ranked:
            return "Belum ada ringkasan percakapan."

        parts = []
        for msg in sorted(ranked, key=lambda item: item.timestamp):
            speaker = "Mas" if msg.from_who == "user" else role_id
            compact = self._compact_text(msg.content, max_len=72)
            parts.append(f"{speaker}: {compact}")
        return " | ".join(parts[:limit])

    def reset_role_history(self, user_id: str, role_id: str) -> None:
        """Hapus semua history untuk satu pasangan user-role."""

        key = (user_id, role_id)
        with self._lock:
            self._data.pop(key, None)

    @staticmethod
    def _score_message(msg: MessageSnippet, query_text: str = "") -> float:
        score = float(msg.timestamp) * 0.001
        text = msg.content.lower()
        query_keywords = set(_tokenize_keywords(query_text))
        msg_keywords = set(_tokenize_keywords(text))

        if msg.from_who == "user":
            score += 25
        if "?" in text:
            score += 12
        if any(keyword in text for keyword in ["janji", "ingat", "nanti", "besok", "kangen", "marah"]):
            score += 18
        if any(keyword in text for keyword in ["sedih", "maaf", "takut", "senang", "sayang", "rindu"]):
            score += 16
        if len(msg.content) > 120:
            score += 8
        if query_keywords:
            overlap = len(query_keywords.intersection(msg_keywords))
            score += overlap * 14
        if any(token in text for token in ["!", "!!", "..."]):
            score += 3

        return score

    @staticmethod
    def _compact_text(text: str, max_len: int = 80) -> str:
        compact = re.sub(r"\s+", " ", text).strip()
        if len(compact) <= max_len:
            return compact
        return compact[: max_len - 3] + "..."


def _tokenize_keywords(text: str) -> List[str]:
    if not text:
        return []
    tokens = re.findall(r"[a-zA-Z0-9_]{3,}", text.lower())
    stopwords = {"yang", "dan", "untuk", "dengan", "atau", "karena", "mas", "aku", "kamu"}
    return [token for token in tokens if token not in stopwords]
