"""LLM client wrapper for SERIVA.

Tujuan:
- Satu pintu untuk memanggil model bahasa (DeepSeek atau lainnya).
- Mudah diganti provider tanpa ubah core logic/role.

Desain:
- Fungsi utama: `generate_text(messages, temperature, max_tokens, **kwargs)`
- `messages` mengikuti gaya chat OpenAI-like:
    [
      {"role": "system", "content": "..."},
      {"role": "user", "content": "..."},
      {"role": "assistant", "content": "..."},
      ...
    ]

Catatan:
- Di sini implementasi default pakai HTTP generic. Sesuaikan URL & header
  dengan provider yang kamu pakai (misal DeepSeek, OpenAI-compatible, dsb.).
- Kalau kamu sudah punya SDK resmi, kamu bisa ganti isi `generate_text` saja.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    """Konfigurasi dasar LLM.

    Ubah nilai default sesuai provider yang kamu pakai.
    """

    api_key: str
    base_url: str  # misal: "https://api.deepseek.com/v1/chat/completions"
    model: str     # misal: "deepseek-chat"

    timeout_seconds: int = 30
    default_temperature: float = 0.85
    default_max_tokens: int = 512


class LLMClient:
    """Client sederhana untuk memanggil LLM dari SERIVA."""

    def __init__(self, config: Optional[LLMConfig] = None) -> None:
        if config is None:
            # Baca dari environment variable sebagai default.
            api_key = os.getenv("LLM_API_KEY", "")
            base_url = os.getenv("LLM_BASE_URL", "")
            model = os.getenv("LLM_MODEL", "")

            if not api_key or not base_url or not model:
                raise RuntimeError(
                    "LLMClient misconfigured: pastikan LLM_API_KEY, LLM_BASE_URL, "
                    "dan LLM_MODEL sudah di-set di environment."
                )

            config = LLMConfig(api_key=api_key, base_url=base_url, model=model)

        self.config = config

    # --------------------------------------------------
    # API utama
    # --------------------------------------------------

    def generate_text(
        self,
        messages: List[Dict[str, str]],
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        extra_params: Optional[Dict[str, Any]] = None,
        **provider_params: Any,
    ) -> str:
        """Panggil LLM dan kembalikan teks jawaban assistant.

        Args:
            messages: daftar pesan dengan key "role" & "content".
            temperature: override temperature (kalau None pakai default).
            max_tokens: override max_tokens (kalau None pakai default).
            extra_params: parameter tambahan untuk provider (opsional).

        Returns:
            String jawaban dari model.

        Raises:
            RuntimeError kalau response tidak valid / error dari API.
        """

        if temperature is None:
            temperature = self.config.default_temperature
        if max_tokens is None:
            max_tokens = self.config.default_max_tokens

        payload: Dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "temperature": float(temperature),
            "max_tokens": int(max_tokens),
        }

        merged_extra_params: Dict[str, Any] = {}
        if extra_params:
            merged_extra_params.update(extra_params)
        if provider_params:
            merged_extra_params.update(provider_params)
        if merged_extra_params:
            payload.update(merged_extra_params)

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        try:
            resp = requests.post(
                self.config.base_url,
                json=payload,
                headers=headers,
                timeout=self.config.timeout_seconds,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Gagal memanggil LLM: %s", exc)
            raise RuntimeError("Gagal memanggil LLM (request error)") from exc

        if resp.status_code != 200:
            logger.error(
                "LLM API error: status=%s body=%s", resp.status_code, resp.text
            )
            raise RuntimeError(
                f"LLM API error: status={resp.status_code}, body={resp.text[:300]}"
            )

        data = resp.json()

        # Struktur ini mengikuti pola OpenAI/DeepSeek-style:
        # {
        #   "choices": [
        #       {"message": {"role": "assistant", "content": "..."}}
        #   ],
        #   ...
        # }
        try:
            choices = data["choices"]
            if not choices:
                raise KeyError("choices kosong")

            message = choices[0]["message"]
            content = message["content"]
            if not isinstance(content, str):
                raise TypeError("content bukan string")

            return content
        except Exception as exc:  # noqa: BLE001
            logger.exception("Response LLM tidak terduga: %s", data)
            raise RuntimeError("Format response LLM tidak dikenal") from exc
