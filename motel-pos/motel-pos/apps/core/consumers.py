"""Authenticated Server-Sent Events consumer for live dashboard updates."""

from __future__ import annotations

import asyncio
import json
from contextlib import suppress
from typing import Any

from channels.consumer import AsyncConsumer
from channels.exceptions import StopConsumer

from apps.core.events import DASHBOARD_GROUP

ALLOWED_ROLES = {"cashier", "manager", "admin"}
HEARTBEAT_SECONDS = 20


class DashboardEventsConsumer(AsyncConsumer):
    """Hold one session-authenticated connection and stream invalidations."""

    async def http_request(self, event: dict[str, Any]) -> None:
        """Authorize and start the stream after the complete GET request arrives."""
        if event.get("more_body") or getattr(self, "_connected", False):
            return
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self._send_response(401, b"Authentication required")
            raise StopConsumer
        if getattr(user, "role", None) not in ALLOWED_ROLES:
            await self._send_response(403, b"Dashboard access required")
            raise StopConsumer

        self._connected = True
        self._send_lock = asyncio.Lock()
        await self.channel_layer.group_add(DASHBOARD_GROUP, self.channel_name)
        await self.send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [
                    (b"Content-Type", b"text/event-stream; charset=utf-8"),
                    (b"Cache-Control", b"no-cache, no-transform"),
                    (b"X-Accel-Buffering", b"no"),
                ],
            }
        )
        await self._send_event("ready", {"connected": True})
        self._heartbeat_task = asyncio.create_task(self._heartbeat())

    async def _send_response(self, status: int, body: bytes) -> None:
        await self.send(
            {"type": "http.response.start", "status": status, "headers": []}
        )
        await self.send(
            {"type": "http.response.body", "body": body, "more_body": False}
        )

    async def http_disconnect(self, event: dict[str, Any]) -> None:
        del event
        if getattr(self, "_connected", False):
            await self.channel_layer.group_discard(
                DASHBOARD_GROUP, self.channel_name
            )
        heartbeat = getattr(self, "_heartbeat_task", None)
        if heartbeat is not None:
            heartbeat.cancel()
            with suppress(asyncio.CancelledError):
                await heartbeat
        raise StopConsumer

    async def _heartbeat(self) -> None:
        while True:
            await asyncio.sleep(HEARTBEAT_SECONDS)
            async with self._send_lock:
                await self.send(
                    {
                        "type": "http.response.body",
                        "body": b": keep-alive\n\n",
                        "more_body": True,
                    }
                )

    async def _send_event(self, event: str, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, separators=(",", ":"), ensure_ascii=True)
        message = f"event: {event}\ndata: {data}\n\n".encode()
        async with self._send_lock:
            await self.send(
                {
                    "type": "http.response.body",
                    "body": message,
                    "more_body": True,
                }
            )

    async def dashboard_update(self, event: dict[str, Any]) -> None:
        """Send a channel-layer invalidation as a named SSE event."""
        if getattr(self, "_connected", False):
            await self._send_event("dashboard.update", event["payload"])
