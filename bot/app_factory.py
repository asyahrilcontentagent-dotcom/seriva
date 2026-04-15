"""Shared helpers untuk bootstrap aplikasi Telegram SERIVA."""

from __future__ import annotations

from telegram.ext import Application, CommandHandler, MessageHandler, filters

from bot.handlers import (
    deal_handler,
    end_session_handler,
    flashback_handler,
    help_handler,
    message_handler,
    mulai_handler,
    nego_handler,
    offline_handler, 
    pause_handler,
    resume_handler,
    role_list_handler,
    set_nova_handler,
    set_role_handler,
    start_handler,
    status_handler,
    venue_handler,
)
from core.llm_client import LLMClient, LLMConfig
from core.orchestrator import Orchestrator
from memory.message_history import MessageHistoryStore
from memory.milestones import MilestoneStore
from memory.story_memory import StoryMemoryStore
from storage.inmemory_store import InMemoryUserStateStore, InMemoryWorldStateStore


def create_orchestrator(
    *,
    llm_api_key: str,
    llm_base_url: str,
    llm_model: str,
    history_limit: int = 50,
) -> Orchestrator:
    """Bangun dependency inti SERIVA dan kembalikan orchestrator siap pakai."""

    user_store = InMemoryUserStateStore()
    world_store = InMemoryWorldStateStore()
    milestone_store = MilestoneStore()
    message_history_store = MessageHistoryStore(max_per_pair=history_limit)
    story_memory_store = StoryMemoryStore()

    llm_cfg = LLMConfig(
        api_key=llm_api_key,
        base_url=llm_base_url,
        model=llm_model,
    )

    return Orchestrator(
        user_store=user_store,
        world_store=world_store,
        llm_client=LLMClient(llm_cfg),
        milestone_store=milestone_store,
        message_history_store=message_history_store,
        story_memory_store=story_memory_store,
    )


def build_application(
    *,
    bot_token: str,
    orchestrator: Orchestrator,
    admin_id: str,
    concurrent_updates: bool = False,
) -> Application:
    """Bangun aplikasi Telegram lengkap dengan semua handler SERIVA."""

    app = (
        Application.builder()
        .token(bot_token)
        .concurrent_updates(concurrent_updates)
        .build()
    )

    app.add_handler(CommandHandler("start", start_handler(orchestrator, admin_id)))
    app.add_handler(CommandHandler("help", help_handler(orchestrator, admin_id)))

    app.add_handler(
        CommandHandler(
            "role",
            role_list_handler(orchestrator, admin_id),
            filters=~filters.Regex(r"^/role\s+"),
        )
    )
    app.add_handler(
        CommandHandler(
            "role",
            set_role_handler(orchestrator, admin_id),
            filters=filters.Regex(r"^/role\s+"),
        )
    )

    app.add_handler(CommandHandler("nova", set_nova_handler(orchestrator, admin_id)))
    app.add_handler(CommandHandler("batal", end_session_handler(orchestrator, admin_id)))
    app.add_handler(CommandHandler("end", end_session_handler(orchestrator, admin_id)))
    app.add_handler(CommandHandler("close", end_session_handler(orchestrator, admin_id)))
    app.add_handler(CommandHandler("status", status_handler(orchestrator, admin_id)))
    app.add_handler(CommandHandler("pause", pause_handler(orchestrator, admin_id)))
    app.add_handler(CommandHandler("resume", resume_handler(orchestrator, admin_id)))
    app.add_handler(CommandHandler("flashback", flashback_handler(orchestrator, admin_id)))
    app.add_handler(CommandHandler("offline", offline_handler(orchestrator, admin_id)))

    app.add_handler(CommandHandler("nego", nego_handler(orchestrator, admin_id)))
    app.add_handler(CommandHandler("deal", deal_handler(orchestrator, admin_id)))
    app.add_handler(CommandHandler("venue", venue_handler(orchestrator, admin_id)))
    app.add_handler(CommandHandler("mulai", mulai_handler(orchestrator, admin_id)))

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            message_handler(orchestrator, admin_id),
        )
    )

    return app
