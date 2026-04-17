"""CodexFlight Bot — Session commands: /new, /current, /threads."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.services.codex_client import CodexClient
from app.services.session_manager import SessionManager

router = Router()


@router.message(Command("new"))
async def cmd_new(
    message: Message,
    codex: CodexClient,
    session_mgr: SessionManager,
) -> None:
    await session_mgr.close(message.chat.id)
    await message.answer(
        "✅ Nueva sesión lista. Envía un mensaje para crear un thread.",
        parse_mode="HTML",
    )


@router.message(Command("current"))
async def cmd_current(
    message: Message,
    session_mgr: SessionManager,
) -> None:
    thread_id = session_mgr.get_thread_id(message.chat.id)
    if not thread_id:
        await message.answer("📋 Sin thread activo. Envía un mensaje para crear uno.")
        return
    await message.answer(f"🟢 Thread: <code>{thread_id}</code>", parse_mode="HTML")


@router.message(Command("threads"))
async def cmd_threads(
    message: Message,
    codex: CodexClient,
) -> None:
    try:
        threads = await codex.thread_list()
        if not threads:
            await message.answer("📋 No hay threads.")
            return

        lines = ["<b>📋 Threads</b>\n"]
        for t in threads[:10]:  # Show max 10
            tid = t.get("id", t.get("threadId", "?"))
            name = t.get("name", "sin nombre")
            archived = "📦 " if t.get("isArchived") else ""
            lines.append(f"  {archived}<code>{tid[:16]}…</code> — {name}")

        await message.answer("\n".join(lines), parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Error: {e}")
