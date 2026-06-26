"""WebSocket inference gateway: receive a msgpack observation, relay it over
ZeroMQ IPC to the inference process, and send the packed result back.

The protocol mirrors openpi's remote inference
(https://github.com/Physical-Intelligence/openpi/blob/main/docs/remote_inference.md):

- transport is a raw WebSocket (the `websockets` library), not HTTP;
- payloads are msgpack with the numpy hooks in `msgpack_numpy`, so observations
  may carry numpy arrays (e.g. images) without a base64/multipart dance;
- on connect the server sends one msgpack metadata frame, then for each request
  it receives a packed observation dict and returns a packed result dict;
- a plain HTTP GET to ``/healthz`` returns 200 OK for liveness checks.

This means an openpi `WebsocketClientPolicy(host, port)` can talk to it directly:
``client.infer(observation)`` round-trips through the ZeroMQ worker.
"""

from __future__ import annotations

import asyncio
import http
import logging
import traceback

import websockets
import websockets.asyncio.server as _server
import websockets.frames

from .config import Settings
from .openpi_client import msgpack_numpy
from .ipc import InferenceClient, InferenceTimeout

logger = logging.getLogger(__name__)


class InferenceServer:
    """WebSocket front door that relays observations to the ZeroMQ backend.

    A single :class:`InferenceClient` (REQ socket) is shared across all
    connections; it serializes concurrent requests internally with a lock, which
    matches the single REP worker on the other end.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        metadata: dict | None = None,
    ) -> None:
        self._settings = settings or Settings.from_env()
        # Sent to every client right after connect (openpi clients read this as
        # `get_server_metadata()`). Keep it small and JSON/msgpack-friendly.
        self._metadata = metadata or {"ipc_endpoint": self._settings.ipc_endpoint}
        self._client = InferenceClient(
            self._settings.ipc_endpoint, self._settings.ipc_timeout_ms
        )

    def serve_forever(self) -> None:
        asyncio.run(self.run())

    async def run(self) -> None:
        self._client.connect()
        try:
            async with _server.serve(
                self._handler,
                self._settings.host,
                self._settings.port,
                compression=None,
                max_size=None,
                process_request=_health_check,
            ) as server:
                logger.info(
                    "anypc websocket gateway listening on ws://%s:%d (backend %s)",
                    self._settings.host,
                    self._settings.port,
                    self._settings.ipc_endpoint,
                )
                await server.serve_forever()
        finally:
            self._client.close()

    async def _handler(self, websocket: _server.ServerConnection) -> None:
        logger.info("connection from %s opened", websocket.remote_address)
        packer = msgpack_numpy.Packer()

        # Handshake: hand the client our metadata frame.
        await websocket.send(packer.pack(self._metadata))

        while True:
            try:
                request = await websocket.recv()
                if isinstance(request, str):
                    request = request.encode("utf-8")
                if len(request) > self._settings.max_message_bytes:
                    raise ValueError(
                        f"message exceeds max of {self._settings.max_message_bytes} bytes"
                    )

                # Relay the packed observation straight through to the worker and
                # return its packed reply untouched — both sides speak msgpack.
                reply = await self._client.request(request)
                await websocket.send(reply)

            except websockets.ConnectionClosed:
                logger.info("connection from %s closed", websocket.remote_address)
                break
            except InferenceTimeout as exc:
                # Backend was too slow. A string frame signals an error to the
                # client (it raises) but keeps the connection open for retries.
                logger.warning("backend timeout: %s", exc)
                await websocket.send(f"inference backend timeout: {exc}")
            except Exception:
                await websocket.send(traceback.format_exc())
                await websocket.close(
                    code=websockets.frames.CloseCode.INTERNAL_ERROR,
                    reason="Internal server error. Traceback included in previous frame.",
                )
                raise


def _health_check(
    connection: _server.ServerConnection, request: _server.Request
) -> _server.Response | None:
    if request.path == "/healthz":
        return connection.respond(http.HTTPStatus.OK, "OK\n")
    # Not a health check — continue with the normal WebSocket handshake.
    return None
