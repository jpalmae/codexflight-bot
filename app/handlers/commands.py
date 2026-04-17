"""CodexFlight Bot — /start, /help, /status commands."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.services.codex_client import CodexClient
from app.services.session_manager import SessionManager

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message, codex: CodexClient, session_mgr: SessionManager) -> None:
    try:
        health = await codex.health()
        status = f"🟢 {health}"
    except Exception:
        status = "🔴 sin conexión"

    text = (
        "<b>⚡ CodexFlight Bot</b>\n"
        "\n"
        f"{status}\n"
        "\n"
        "Envía texto para chatear con Codex.\n"
        "Comandos:\n"
        "  /new — nueva sesión\n"
        "  /current — sesión activa\n"
        "  /stop — detener\n"
        "  /threads — listar threads\n"
        "  /help — manual\n"
    )
    await message.answer(text, parse_mode="HTML")


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    text = (
        "<b>📖 CodexFlight Manual</b>\n"
        "\n"
        "Envía cualquier texto para chatear con Codex (OpenAI).\n"
        "Codex tiene acceso completo al filesystem y shell.\n"
        "\n"
        "<b>Sesiones (Threads):</b>\n"
        "  /new — crear nueva sesión\n"
        "  /current — sesión activa\n"
        "  /threads — listar threads\n"
        "\n"
        "<b>Ejecución:</b>\n"
        "  /stop — detener respuesta\n"
        "\n"
        "<b>Sistema:</b>\n"
        "  /status — estado\n"
    )
    await message.answer(text, parse_mode="HTML")


@router.message(Command("status"))
async def cmd_status(message: Message, codex: CodexClient, session_mgr: SessionManager) -> None:
    lines = ["<b>📊 Estado</b>\n"]

    try:
        health = await codex.health()
        lines.append(f"🟢 {health}")
    except Exception as e:
        lines.append(f"🔴 error: {e}")

    thread_id = session_mgr.get_thread_id(message.chat.id)
    if thread_id:
        lines.append(f"💬 thread: <code>{thread_id[:16]}…</code>")
    else:
        lines.append("💬 thread: ninguno")

    await message.answer("\n".join(lines), parse_mode="HTML")
