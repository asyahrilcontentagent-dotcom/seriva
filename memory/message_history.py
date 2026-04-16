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


@dataclass
class ScoredMessage:
    snippet: MessageSnippet
    score: float
    memory_type: str


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
        min_score: float = 0.0,
    ) -> List[MessageSnippet]:
        """Ambil pesan paling relevan berdasarkan recency + bobot emosional + keyword."""

        recent = self.get_recent_messages(user_id, role_id, limit=max(limit * 4, 20))
        scored = sorted(
            (
                ScoredMessage(
                    snippet=msg,
                    score=self._score_message(msg, query_text=query_text),
                    memory_type=self._classify_memory_type(msg),
                )
                for msg in recent
            ),
            key=lambda item: item.score,
            reverse=True,
        )
        filtered = [item.snippet for item in scored if item.score >= min_score]
        return filtered[:limit]

    def get_memory_packet(
        self,
        user_id: str,
        role_id: str,
        *,
        query_text: str = "",
        top_k: int = 6,
        min_score: float = 25.0,
    ) -> dict:
        """Bangun paket memory yang lebih ketat dan siap pakai."""

        recent = self.get_recent_messages(user_id, role_id, limit=max(top_k * 5, 30))
        scored_items = sorted(
            (
                ScoredMessage(
                    snippet=msg,
                    score=self._score_message(msg, query_text=query_text),
                    memory_type=self._classify_memory_type(msg),
                )
                for msg in recent
            ),
            key=lambda item: item.score,
            reverse=True,
        )

        kept = [item for item in scored_items if item.score >= min_score][:top_k]
        if not kept:
            kept = scored_items[: min(3, len(scored_items))]

        short_term = [item for item in kept if item.memory_type == "short_term"][:3]
        key_events = [item for item in kept if item.memory_type == "key_event"][:3]
        long_term = [item for item in kept if item.memory_type == "long_term"][:2]

        return {
            "items": kept,
            "short_term": short_term,
            "key_events": key_events,
            "long_term": long_term,
        }

    def summarize_recent_messages(
        self,
        user_id: str,
        role_id: str,
        limit: int = 6,
        query_text: str = "",
        min_score: float = 25.0,
    ) -> str:
        packet = self.get_memory_packet(
            user_id,
            role_id,
            query_text=query_text,
            top_k=limit,
            min_score=min_score,
        )
        ranked = [item.snippet for item in packet["items"]]
        if not ranked:
            return "Belum ada ringkasan percakapan."

        parts = []
        for msg in sorted(ranked, key=lambda item: item.timestamp):
            speaker = "Mas" if msg.from_who == "user" else role_id
            compact = self._compact_text(msg.content, max_len=72)
            parts.append(f"{speaker}: {compact}")
        return " | ".join(parts[:limit])

    def summarize_memory_tiers(
        self,
        user_id: str,
        role_id: str,
        *,
        query_text: str = "",
        top_k: int = 6,
        min_score: float = 25.0,
    ) -> dict:
        packet = self.get_memory_packet(
            user_id,
            role_id,
            query_text=query_text,
            top_k=top_k,
            min_score=min_score,
        )

        return {
            "short_term": self._summarize_bucket(packet["short_term"], role_id),
            "key_events": self._summarize_bucket(packet["key_events"], role_id),
            "long_term_candidates": self._summarize_bucket(packet["long_term"], role_id),
            "selected_count": len(packet["items"]),
        }

    def reset_role_history(self, user_id: str, role_id: str) -> None:
        """Hapus semua history untuk satu pasangan user-role."""

        key = (user_id, role_id)
        with self._lock:
            self._data.pop(key, None)

    @staticmethod
    def _score_message(msg: MessageSnippet, query_text: str = "") -> float:
        score = 0.0
        text = msg.content.lower()
        query_keywords = set(_tokenize_keywords(query_text))
        msg_keywords = set(_tokenize_keywords(text))

        score += MessageHistoryStore._recency_score(msg.timestamp)
        score += MessageHistoryStore._semantic_relevance_score(query_text, text)
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
    def _classify_memory_type(msg: MessageSnippet) -> str:
        text = msg.content.lower()
        if any(
            keyword in text
            for keyword in ["janji", "ingat", "selalu", "pertama", "marah", "maaf", "sayang", "rindu", "besok", "nanti"]
        ):
            return "key_event"
        if len(text) <= 80:
            return "short_term"
        return "long_term"

    @staticmethod
    def _summarize_bucket(items: List[ScoredMessage], role_id: str) -> str:
        if not items:
            return "-"
        parts = []
        for item in sorted(items, key=lambda entry: entry.snippet.timestamp):
            msg = item.snippet
            speaker = "Mas" if msg.from_who == "user" else role_id
            parts.append(f"{speaker}: {MessageHistoryStore._compact_text(msg.content, max_len=60)}")
        return " | ".join(parts[:3])

    @staticmethod
    def _recency_score(timestamp: float) -> float:
        # Timestamp besar tetap dibatasi agar skor tidak didominasi nilai waktu mentah.
        coarse = int(timestamp) % 100000
        return min(22.0, coarse / 5000)

    @staticmethod
    def _semantic_relevance_score(query_text: str, text: str) -> float:
        if not query_text.strip() or not text.strip():
            return 0.0

        query_tokens = set(_tokenize_keywords(query_text))
        text_tokens = set(_tokenize_keywords(text))
        if not query_tokens or not text_tokens:
            return 0.0

        intersection = len(query_tokens.intersection(text_tokens))
        union = max(1, len(query_tokens.union(text_tokens)))
        token_jaccard = intersection / union

        query_ngrams = _char_ngrams(query_text.lower())
        text_ngrams = _char_ngrams(text.lower())
        if not query_ngrams or not text_ngrams:
            char_jaccard = 0.0
        else:
            char_jaccard = len(query_ngrams.intersection(text_ngrams)) / max(1, len(query_ngrams.union(text_ngrams)))

        return (token_jaccard * 45.0) + (char_jaccard * 20.0)

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


def _char_ngrams(text: str, n: int = 3) -> set[str]:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) < n:
        return {compact} if compact else set()
    return {compact[i : i + n] for i in range(len(compact) - n + 1)}
