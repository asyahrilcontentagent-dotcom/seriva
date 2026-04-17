"""SERIVA webhook entrypoint untuk Railway."""

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


_configure_logging()
logger = logging.getLogger(__name__)


def _alias_deepseek_to_llm() -> None:
    llm_key = os.getenv("LLM_API_KEY")
    deepseek_key = os.getenv("DEEPSEEK_API_KEY")

    if not llm_key and deepseek_key:
        os.environ["LLM_API_KEY"] = deepseek_key
        logger.info("LLM_API_KEY tidak ada, menggunakan DEEPSEEK_API_KEY sebagai gantinya.")


def main() -> None:
    _alias_deepseek_to_llm()

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    admin_id = os.getenv("SERIVA_ADMIN_ID")
    webhook_url = os.getenv("WEBHOOK_URL")
    port = int(os.getenv("PORT", "8080"))

    if not bot_token or not admin_id:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN dan SERIVA_ADMIN_ID harus di-set di environment."
        )

    if not webhook_url:
        raise RuntimeError(
            "WEBHOOK_URL harus di-set di environment untuk mode webhook."
        )

    llm_api_key = os.getenv("LLM_API_KEY")
    llm_base_url = os.getenv("LLM_BASE_URL")
    llm_model = os.getenv("LLM_MODEL")

    if not llm_api_key or not llm_base_url or not llm_model:
        raise RuntimeError(
            "LLM_API_KEY, LLM_BASE_URL, dan LLM_MODEL harus di-set di environment "
            "(atau DEEPSEEK_API_KEY diisi sehingga LLM_API_KEY otomatis terisi)."
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

    logger.info("SERIVA Telegram bot starting (webhook mode)...")
    logger.info("Webhook URL: %s", webhook_url)
    logger.info("Listening on 0.0.0.0:%d", port)

    app.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path="/webhook",
        webhook_url=webhook_url,
    )


if __name__ == "__main__":
    main()
