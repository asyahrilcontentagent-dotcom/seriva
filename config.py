"""Global configuration helper untuk SERIVA.

Membaca environment variables yang dibutuhkan untuk runtime:
- TELEGRAM_BOT_TOKEN
- SERIVA_ADMIN_ID
- LLM_API_KEY
- LLM_BASE_URL
- LLM_MODEL

File ini tidak mengubah perilaku bot, hanya menyediakan satu tempat
untuk mengambil config jika diperlukan.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class TelegramConfig:
    bot_token: str
    admin_id: str


@dataclass
class LLMConfigRuntime:
    api_key: str
    base_url: str
    model: str


@dataclass
class SERIVAConfig:
    telegram: TelegramConfig
    llm: LLMConfigRuntime


def load_config() -> SERIVAConfig:
    """Membaca config dari environment dan mengembalikan SERIVAConfig.

    Raises:
        RuntimeError: jika ada env yang wajib tapi tidak di-set.
    """

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    admin_id = os.getenv("SERIVA_ADMIN_ID")

    if not bot_token or not admin_id:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN dan SERIVA_ADMIN_ID harus di-set di environment."
        )

    llm_api_key = os.getenv("LLM_API_KEY")
    llm_base_url = os.getenv("LLM_BASE_URL")
    llm_model = os.getenv("LLM_MODEL")

    if not llm_api_key or not llm_base_url or not llm_model:
        raise RuntimeError(
            "LLM_API_KEY, LLM_BASE_URL, dan LLM_MODEL harus di-set di environment."
        )

    telegram_cfg = TelegramConfig(bot_token=bot_token, admin_id=admin_id)
    llm_cfg = LLMConfigRuntime(api_key=llm_api_key, base_url=llm_base_url, model=llm_model)

    return SERIVAConfig(telegram=telegram_cfg, llm=llm_cfg)
