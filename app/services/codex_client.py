"""CodexFlight Bot — WebSocket JSON-RPC client for Codex App Server.

Communicates with `codex app-server` via WebSocket using JSON-RPC 2.0.

Protocol flow:
1. Connect to ws://host:port
2. thread/start → creates a thread, returns threadId
3. turn/start (threadId + input) → starts a turn, streams notifications
4. Server sends notifications: AgentMessageDeltaNotification, TurnCompletedNotification, etc.
5. Server may send ClientRequest for approval → respond with approval response

Key differences from Gooseflight:
- WebSocket (not subprocess stdout or HTTP/SSE)
- JSON-RPC 2.0 with id/method/params
- Threads instead of named sessions
- Bidirectional: server can request approvals from client
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from typing import AsyncIterator, Callable

import websockets

from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)


class CodexClient:
    """Async client for Codex App Server via WebSocket JSON-RPC 2.0.

    Manages a single WebSocket connection and multiplexes thread/turn
    operations. The connection auto-reconnects on failure.
    """

    def __init__(self) -> None:
        self._ws_url = settings.codex_ws_url
        self._ws: websockets.WebSocketClientProtocol | None = None
        self._id_counter: int = 0
        self._pending: dict[int | str, asyncio.Future] = {}  # rpc_id -> Future
        self._notifications: asyncio.Queue[dict] = asyncio.Queue()
        self._recv_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        self._approval_handler: Callable | None = None

    # ── Connection management ─────────────────────────────

    async def connect(self) -> None:
        """Establish WebSocket connection and start receive loop."""
        async with self._lock:
            if self._ws and self._ws.open:
                return
            await self._connect_internal()

    async def _connect_internal(self) -> None:
        """Internal connect without lock (caller must hold lock or be init)."""
        logger.info("ws_connecting", url=self._ws_url)
        self._ws = await websockets.connect(
            self._ws_url,
            max_size=50 * 1024 * 1024,  # 50MB
            ping_interval=30,
            ping_timeout=10,
        )
        self._recv_task = asyncio.create_task(self._recv_loop())
        logger.info("ws_connected")

    async def ensure_connected(self) -> None:
        """Ensure we have an active connection."""
        if self._ws and self._ws.open:
            return
        async with self._lock:
            if self._ws and self._ws.open:
                return
            # Clean up old connection
            if self._recv_task:
                self._recv_task.cancel()
                try:
                    await self._recv_task
                except asyncio.CancelledError:
                    pass
            await self._connect_internal()

    async def close(self) -> None:
        """Close the WebSocket connection."""
        if self._recv_task:
            self._recv_task.cancel()
            try:
                await self._recv_task
            except asyncio.CancelledError:
                pass
        if self._ws:
            await self._ws.close()
            self._ws = None
        # Cancel any pending futures
        for fut in self._pending.values():
            if not fut.done():
                fut.cancel()
        self._pending.clear()
        logger.info("ws_closed")

    # ── Receive loop ──────────────────────────────────────

    async def _recv_loop(self) -> None:
        """Background task that reads messages from WebSocket."""
        try:
            async for raw in self._ws:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    logger.warning("ws_parse_error", raw=raw[:200])
                    continue

                await self._handle_message(msg)
        except websockets.ConnectionClosed as e:
            logger.warning("ws_closed_remote", code=e.code, reason=e.reason)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("ws_recv_error", error=str(e))

    async def _handle_message(self, msg: dict) -> None:
        """Route incoming JSON-RPC message."""
        # JSON-RPC Response (has "id") — resolve pending future
        if "id" in msg and ("result" in msg or "error" in msg):
            rpc_id = msg["id"]
            fut = self._pending.pop(rpc_id, None)
            if fut and not fut.done():
                if "error" in msg:
                    fut.set_exception(
                        RuntimeError(f"JSON-RPC error: {msg['error']}")
                    )
                else:
                    fut.set_result(msg.get("result"))
            return

        # JSON-RPC Notification or Server Request
        method = msg.get("method", "")

        # Server → Client request (e.g. approval prompt)
        if "id" in msg and method:
            await self._handle_server_request(msg)
            return

        # Notification (no id, has method)
        if method:
            await self._notifications.put(msg)
            return

        logger.warning("ws_unhandled_message", msg=str(msg)[:300])

    async def _handle_server_request(self, msg: dict) -> None:
        """Handle a request from the server (e.g. approval prompt)."""
        method = msg.get("method", "")
        rpc_id = msg["id"]
        params = msg.get("params", {})

        logger.info("server_request", method=method, rpc_id=rpc_id)

        if self._approval_handler:
            try:
                result = await self._approval_handler(method, params)
                await self._send_response(rpc_id, result)
            except Exception as e:
                await self._send_error(rpc_id, str(e))
        else:
            # No handler — auto-approve everything
            await self._send_response(rpc_id, {"approved": True})

    # ── JSON-RPC sending ──────────────────────────────────

    def _next_id(self) -> int:
        self._id_counter += 1
        return self._id_counter

    async def _send_request(self, method: str, params: dict, timeout: float = 120.0) -> dict:
        """Send a JSON-RPC request and wait for the response."""
        await self.ensure_connected()

        rpc_id = self._next_id()
        payload = {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "method": method,
            "params": params,
        }

        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[rpc_id] = fut

        await self._ws.send(json.dumps(payload))
        logger.info("rpc_sent", method=method, rpc_id=rpc_id)

        try:
            result = await asyncio.wait_for(fut, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            self._pending.pop(rpc_id, None)
            raise TimeoutError(f"RPC {method} timed out after {timeout}s")

    async def _send_notification(self, method: str, params: dict) -> None:
        """Send a JSON-RPC notification (no response expected)."""
        await self.ensure_connected()
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }
        await self._ws.send(json.dumps(payload))

    async def _send_response(self, rpc_id: int | str, result: dict) -> None:
        """Send a JSON-RPC response to a server request."""
        await self.ensure_connected()
        payload = {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "result": result,
        }
        await self._ws.send(json.dumps(payload))

    async def _send_error(self, rpc_id: int | str, error: str, code: int = -32000) -> None:
        """Send a JSON-RPC error response."""
        await self.ensure_connected()
        payload = {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "error": {"code": code, "message": error},
        }
        await self._ws.send(json.dumps(payload))

    # ── Notification streaming ────────────────────────────

    async def notifications(self, thread_id: str) -> AsyncIterator[dict]:
        """Yield notifications for a specific thread until turn completes.

        Filters by threadId from AgentMessageDeltaNotification,
        TurnCompletedNotification, etc.
        """
        while True:
            msg = await self._notifications.get()
            method = msg.get("method", "")
            params = msg.get("params", {})

            # Filter by threadId
            msg_thread = params.get("threadId", "")
            if msg_thread and msg_thread != thread_id:
                # Not for us — put back (simplified: just skip)
                continue

            yield {"method": method, "params": params}

            # Stop on turn completed
            if method == "turn/completed":
                break

    # ── High-level API ────────────────────────────────────

    async def thread_start(self, cwd: str | None = None) -> dict:
        """Create a new Codex thread.

        Returns the thread object with threadId, model, sandbox, etc.
        """
        params: dict = {
            "sandbox": settings.codex_sandbox,
            "approvalPolicy": settings.codex_approval_policy,
            "personality": settings.codex_personality,
            "serviceName": settings.codex_service_name,
        }

        if cwd:
            params["cwd"] = cwd
        if settings.codex_model:
            params["model"] = settings.codex_model
        if settings.codex_model_provider:
            params["modelProvider"] = settings.codex_model_provider
        if settings.codex_base_instructions:
            params["baseInstructions"] = settings.codex_base_instructions

        result = await self._send_request("thread/start", params)
        logger.info("thread_started", result=str(result)[:200])
        return result

    async def turn_start(
        self,
        thread_id: str,
        message: str,
    ) -> AsyncIterator[dict]:
        """Send a message to a thread and yield streaming notifications.

        This is the main interaction: sends turn/start, then yields
        AgentMessageDeltaNotification events until TurnCompletedNotification.
        """
        params = {
            "threadId": thread_id,
            "input": [{"type": "text", "text": message}],
        }

        # Send the turn/start request (returns immediately with turn info)
        turn_result = await self._send_request("turn/start", params, timeout=30.0)
        logger.info("turn_started", thread_id=thread_id)

        # Now stream notifications until turn completes
        async for event in self.notifications(thread_id):
            yield event

    async def turn_interrupt(self, thread_id: str) -> dict:
        """Interrupt the current turn."""
        return await self._send_request("turn/interrupt", {
            "threadId": thread_id,
        })

    async def thread_list(self) -> list[dict]:
        """List all threads."""
        result = await self._send_request("thread/list", {})
        return result if isinstance(result, list) else []

    async def thread_archive(self, thread_id: str) -> dict:
        """Archive a thread."""
        return await self._send_request("thread/archive", {"threadId": thread_id})

    async def health(self) -> str:
        """Check Codex App Server connectivity."""
        try:
            await self.ensure_connected()
            # Try a lightweight call
            result = await self._send_request("thread/list", {}, timeout=10.0)
            return "codex app-server ✓ (connected)"
        except Exception as e:
            return f"codex app-server ✗ ({e})"

    def set_approval_handler(self, handler: Callable) -> None:
        """Set a callback for handling server approval requests.

        Handler signature: async handler(method: str, params: dict) -> dict
        """
        self._approval_handler = handler
