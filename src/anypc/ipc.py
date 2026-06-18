"""Async ZeroMQ client that relays a request to the inference process.

Uses a REQ socket over the configured endpoint. The inference process is the
stable peer and binds a REP socket; this client connects to it.

Wire format (multipart):
    request : [ json(metadata) , raw_image_bytes ]
    reply   : [ json(result) ]
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import zmq
import zmq.asyncio


class InferenceTimeout(Exception):
    """Raised when the inference backend does not reply within the timeout."""


class InferenceClient:
    """Serialized async REQ client for the inference backend.

    A REQ socket enforces a strict send→recv cycle, so concurrent FastAPI
    requests are serialized with a lock. On timeout the socket is in an
    unrecoverable state and is rebuilt before the next request.
    """

    def __init__(self, endpoint: str, timeout_ms: int) -> None:
        self._endpoint = endpoint
        self._timeout_ms = timeout_ms
        self._ctx = zmq.asyncio.Context.instance()
        self._lock = asyncio.Lock()
        self._sock: zmq.asyncio.Socket | None = None

    def connect(self) -> None:
        self._sock = self._open_socket()

    def _open_socket(self) -> "zmq.asyncio.Socket":
        sock = self._ctx.socket(zmq.REQ)
        # Don't linger on close, and fail fast instead of queuing forever.
        sock.setsockopt(zmq.LINGER, 0)
        sock.connect(self._endpoint)
        return sock

    def _reset_socket(self) -> None:
        if self._sock is not None:
            self._sock.close(linger=0)
        self._sock = self._open_socket()

    async def request(self, metadata: dict[str, Any], image: bytes) -> dict[str, Any]:
        """Send metadata + image, return the backend's JSON reply as a dict."""
        if self._sock is None:
            self.connect()

        async with self._lock:
            assert self._sock is not None
            await self._sock.send_multipart(
                [json.dumps(metadata).encode("utf-8"), image]
            )

            events = await self._sock.poll(self._timeout_ms, zmq.POLLIN)
            if not events:
                # REQ is stuck waiting for a reply; rebuild it.
                self._reset_socket()
                raise InferenceTimeout(
                    f"no reply within {self._timeout_ms} ms from {self._endpoint}"
                )

            reply = await self._sock.recv_multipart()

        payload = reply[0] if reply else b"{}"
        return json.loads(payload.decode("utf-8"))

    def close(self) -> None:
        if self._sock is not None:
            self._sock.close(linger=0)
            self._sock = None
