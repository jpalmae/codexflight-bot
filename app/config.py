"""CodexFlight Bot — Configuration via pydantic-settings."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


def _read_secret(path: Optional[str]) -> Optional[str]:
    """Read a Docker secret file if provided, return None otherwise."""
    if not path:
        return None
    p = Path(path)
    if p.exists():
        return p.read_text().strip()
    return None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Telegram ──────────────────────────────────────────
    telegram_bot_token: str = ""
    telegram_bot_token_file: str = ""
    authorized_user_id: int = 0

    # ── Codex App Server ──────────────────────────────────
    codex_ws_url: str = "ws://localhost:8295"
    codex_sandbox: str = "danger-full-access"  # read-only | workspace-write | danger-full-access
    codex_approval_policy: str = "never"  # untrusted | on-failure | on-request | never
    codex_personality: str = "pragmatic"  # none | friendly | pragmatic
    codex_service_name: str = "codexflight-bot"
    codex_model: str = ""  # empty = use Codex default (o3)
    codex_model_provider: str = ""  # empty = use Codex default
    codex_base_instructions: str = ""  # additional system instructions

    # ── Paths ─────────────────────────────────────────────
    data_dir: str = "/data"
    sqlite_path: str = ""  # computed if empty
    workspace_dir: str = "/workspace"

    # ── Behaviour ─────────────────────────────────────────
    stream_edit_interval_seconds: float = 1.5
    completion_notif_threshold_seconds: int = 30

    # ── Logging ───────────────────────────────────────────
    log_level: str = "INFO"
    log_format: str = "json"  # json | console
    tz: str = "America/Santiago"

    # ── Resolved properties ───────────────────────────────

    @property
    def resolved_token(self) -> str:
        return _read_secret(self.telegram_bot_token_file) or self.telegram_bot_token

    @property
    def resolved_sqlite_path(self) -> str:
        if self.sqlite_path:
            return self.sqlite_path
        return os.path.join(self.data_dir, "bot.sqlite")


settings = Settings()
