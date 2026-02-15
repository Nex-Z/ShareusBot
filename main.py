from __future__ import annotations

import logging

from ncatbot.core import BotClient
from ncatbot.core.event import MetaEvent

from plugins.archive import register_archive_handlers
from plugins.blacklist import register_blacklist_handlers
from plugins.common import AppContext
from plugins.group_admin import register_group_admin_handlers
from plugins.query import register_query_handlers
from plugins.scheduler import register_scheduler_handlers
from shared.config import get_settings
from shared.database import get_session_factory, init_database


def _setup_logging(debug: bool) -> None:
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level = level,
        format = "%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


def build_bot() -> BotClient:
    settings = get_settings()
    _setup_logging(settings.debug)
    init_database(settings.database_url, echo = settings.sql_echo)

    ctx = AppContext(
        settings = settings,
        session_factory = get_session_factory(),
    )

    bot = BotClient()
    register_blacklist_handlers(bot, ctx)
    register_query_handlers(bot, ctx)
    register_archive_handlers(bot, ctx)
    register_group_admin_handlers(bot, ctx)
    register_scheduler_handlers(bot, ctx)

    @bot.on_startup()
    async def on_startup(event: MetaEvent) -> None:
        logging.getLogger(__name__).info("Bot startup: %s", event.self_id)
        # if settings.auto_create_tables:
        # await create_all_tables()
        # logging.getLogger(__name__).info("Database tables initialized.")

    return bot


if __name__ == "__main__":
    build_bot().run_frontend()
