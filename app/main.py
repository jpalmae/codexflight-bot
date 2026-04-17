"""CodexFlight Bot — Entry point."""

from __future__ import annotations

import asyncio
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.config import settings
from app.db.init import init_db
from app.handlers import build_router
from app.logging_config import get_logger, setup_logging
from app.middlewares.auth import SingleUserAuthMiddleware
from app.services.codex_client import CodexClient
from app.services.session_manager import SessionManager


class ServiceInjector:
    """Inject shared services into handler kwargs."""

    def __init__(self, codex: CodexClient, session_mgr: SessionManager):
        self.codex = codex
        self.session_mgr = session_mgr

    async def __call__(self, handler, event, data):
        data["codex"] = self.codex
        data["session_mgr"] = self.session_mgr
        return await handler(event, data)


async def main() -> None:
    setup_logging(level=settings.log_level, fmt=settings.log_format)
    log = get_logger("main")

    token = settings.resolved_token
    if not token:
        print("ERROR: TELEGRAM_BOT_TOKEN not set")
        sys.exit(1)

    if not settings.authorized_user_id:
        print("ERROR: AUTHORIZED_USER_ID not set")
        sys.exit(1)

    await init_db()

    bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    dp.update.middleware(SingleUserAuthMiddleware(settings.authorized_user_id))

    codex = CodexClient()
    session_mgr = SessionManager()
    dp.update.outer_middleware(ServiceInjector(codex, session_mgr))
    dp.include_router(build_router())

    await bot.delete_webhook(drop_pending_updates=True)

    # Connect to Codex App Server
    try:
        await codex.connect()
        health = await codex.health()
    except Exception as e:
        log.warning("codex_connect_failed", error=str(e))
        health = f"⚠️ No conectado: {e}"

    log.info("bot_starting", user_id=settings.authorized_user_id)

    try:
        await bot.send_message(
            settings.authorized_user_id,
            f"⚡ CodexFlight Bot online\n{health}",
        )
    except Exception:
        pass

    try:
        await dp.start_polling(
            bot,
            allowed_updates=["message", "edited_message", "callback_query"],
            polling_timeout=30,
        )
    finally:
        await codex.close()
        await bot.session.close()
        log.info("bot_stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
