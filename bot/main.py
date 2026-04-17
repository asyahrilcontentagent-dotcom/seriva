"""Entrypoint Telegram bot untuk SERIVA (polling-based)."""

from __future__ import annotations

import logging
import os

from bot.app_factory import build_application, create_orchestrator


def _configure_logging() -> None:
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)
    logging.getLogger("telegram.ext").setLevel(logging.WARNING)


def _alias_deepseek_to_llm() -> None:
    llm_key = os.getenv("LLM_API_KEY")
    deepseek_key = os.getenv("DEEPSEEK_API_KEY")
    if not llm_key and deepseek_key:
        os.environ["LLM_API_KEY"] = deepseek_key


_configure_logging()
logger = logging.getLogger(__name__)


def main() -> None:
    _alias_deepseek_to_llm()
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

    orchestrator = create_orchestrator(
        llm_api_key=llm_api_key,
        llm_base_url=llm_base_url,
        llm_model=llm_model,
    )
    app = build_application(
        bot_token=bot_token,
        orchestrator=orchestrator,
        admin_id=admin_id,
        concurrent_updates=False,
    )

    logger.info("SERIVA Telegram bot starting (polling mode)...")
    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=["message"],
    )


if __name__ == "__main__":
    main()
