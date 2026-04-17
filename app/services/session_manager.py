"""CodexFlight Bot — Session manager mapping Telegram chats to Codex threads."""

from __future__ import annotations

from app.logging_config import get_logger

logger = get_logger(__name__)


class SessionManager:
    """Maps Telegram chats to Codex threads.

    Each Telegram chat gets one active thread at a time.
    Tracks threadId so we can resume conversations.
    """

    def __init__(self) -> None:
        self._threads: dict[int, str] = {}  # chat_id -> threadId
        self._has_session: dict[int, bool] = {}  # chat_id -> True if thread exists

    def get_thread_id(self, chat_id: int) -> str | None:
        """Get the current thread ID for a chat."""
        return self._threads.get(chat_id)

    def set_thread_id(self, chat_id: int, thread_id: str) -> None:
        """Assign a thread ID to a chat."""
        self._threads[chat_id] = thread_id
        self._has_session[chat_id] = True
        logger.info("thread_bound", chat_id=chat_id, thread_id=thread_id)

    def has_session(self, chat_id: int) -> bool:
        """Check if the chat has an existing thread."""
        return self._has_session.get(chat_id, False)

    def mark_created(self, chat_id: int) -> None:
        """Mark that a thread has been created for this chat."""
        self._has_session[chat_id] = True

    async def close(self, chat_id: int) -> None:
        """Clear the session for a chat (e.g. /new command)."""
        self._threads.pop(chat_id, None)
        self._has_session.pop(chat_id, None)
