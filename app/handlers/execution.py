"""CodexFlight Bot — /stop command."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.services.codex_client import CodexClient
from app.services.session_manager import SessionManager

router = Router()


@router.message(Command("stop"))
async def cmd_stop(
    message: Message,
    codex: CodexClient,
    session_mgr: SessionManager,
) -> None:
    thread_id = session_mgr.get_thread_id(message.chat.id)
    if not thread_id:
        await message.answer("No hay thread activo.")
        return
    try:
        await codex.turn_interrupt(thread_id)
        await message.answer("⏹ Detenido.")
    except Exception as e:
        await message.answer(f"⚠️ Error al detener: {e}")
