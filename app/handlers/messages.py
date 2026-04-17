"""CodexFlight Bot — Free text handler: sends prompt to Codex and streams response."""

from __future__ import annotations

import asyncio
import time

from aiogram import Router, F
from aiogram.types import Message

from app.config import settings
from app.logging_config import get_logger
from app.services.codex_client import CodexClient
from app.services.session_manager import SessionManager
from app.services.stream_renderer import StreamRenderer
from app.utils.markdown import markdown_to_tg_html, split_message

logger = get_logger(__name__)

router = Router()


@router.message(F.text, ~F.text.startswith("/"))
async def handle_text(
    message: Message,
    codex: CodexClient,
    session_mgr: SessionManager,
) -> None:
    prompt = message.text
    if not prompt or not prompt.strip():
        return

    chat_id = message.chat.id
    thread_id = session_mgr.get_thread_id(chat_id)

    # Create thread if needed
    if not thread_id:
        try:
            result = await codex.thread_start(cwd=settings.workspace_dir)
            thread_id = result.get("threadId") or result.get("thread", {}).get("id", "")
            if not thread_id:
                await message.answer("❌ Error: no se recibió threadId del servidor.")
                return
            session_mgr.set_thread_id(chat_id, thread_id)
        except Exception as e:
            logger.error("thread_start_error", error=str(e))
            await message.answer(f"❌ Error creando thread: {e}")
            return

    placeholder = await message.answer("⏳ pensando...")

    renderer = StreamRenderer(
        bot=message.bot,
        chat_id=chat_id,
        message_id=placeholder.message_id,
    )

    start_time = time.monotonic()
    full_text = ""
    got_response = False

    try:
        async for event in codex.turn_start(thread_id, prompt):
            method = event.get("method", "")
            params = event.get("params", {})

            if method == "agentMessage/delta":
                # Incremental text delta from Codex
                delta = params.get("delta", "")
                if delta:
                    full_text += delta
                    got_response = True
                    await renderer.update(full_text)

            elif method == "turn/completed":
                # Turn finished — finalize rendering
                await renderer.finalize()
                break

            elif method == "error":
                error_msg = params.get("error", "Error desconocido")
                await renderer.finalize()
                await message.answer(f"❌ {error_msg}")
                break

            elif method == "item/guardianApprovalReviewStarted":
                # Codex is asking for approval — notify user
                tool_name = params.get("toolName", "acción")
                await message.answer(f"🔐 Codex solicita aprobación: <b>{tool_name}</b>", parse_mode="HTML")

            elif method == "item/guardianApprovalReviewCompleted":
                approved = params.get("approved", False)
                emoji = "✅" if approved else "❌"
                await message.answer(f"{emoji} Aprobación {'aceptada' if approved else 'denegada'}")

    except asyncio.CancelledError:
        await renderer.finalize()
        return
    except Exception as e:
        logger.error("stream_error", error=str(e), thread_id=thread_id)
        await renderer.finalize()
        await message.answer(f"❌ Error: {e}")
        return

    if got_response:
        session_mgr.mark_created(chat_id)

    # Final message with HTML rendering
    if full_text.strip():
        html = markdown_to_tg_html(full_text)
        chunks = split_message(html, max_len=4000)
        try:
            await message.bot.edit_message_text(
                chat_id=chat_id,
                message_id=placeholder.message_id,
                text=chunks[0],
                parse_mode="HTML",
            )
        except Exception:
            pass
        for chunk in chunks[1:]:
            try:
                await message.answer(chunk, parse_mode="HTML")
            except Exception:
                await message.answer(chunk)

    elapsed = time.monotonic() - start_time
    if elapsed > settings.completion_notif_threshold_seconds:
        mins = int(elapsed // 60)
        secs = int(elapsed % 60)
        dur = f"{mins}m {secs}s" if mins else f"{secs}s"
        await message.answer(f"✅ Listo en {dur}")
