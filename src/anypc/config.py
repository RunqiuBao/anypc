"""Runtime configuration, sourced from ANYPC_* environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass

# Default ZeroMQ endpoint. ipc:// is a local unix-domain socket (true IPC);
# switch to tcp://host:port if the inference process runs elsewhere.
DEFAULT_IPC_ENDPOINT = "ipc:///tmp/anypc-inference.ipc"


@dataclass(frozen=True)
class Settings:
    """Server settings with environment-variable overrides."""

    host: str = "0.0.0.0"
    port: int = 8000
    # ZeroMQ endpoint of the inference backend (the REP/server side binds it).
    ipc_endpoint: str = DEFAULT_IPC_ENDPOINT
    # How long to wait for the backend to reply before signaling a timeout.
    ipc_timeout_ms: int = 30_000
    # Reject WebSocket messages larger than this (bytes). Default 25 MiB.
    max_message_bytes: int = 25 * 1024 * 1024

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            host=os.getenv("ANYPC_HOST", cls.host),
            port=int(os.getenv("ANYPC_PORT", cls.port)),
            ipc_endpoint=os.getenv("ANYPC_IPC_ENDPOINT", cls.ipc_endpoint),
            ipc_timeout_ms=int(os.getenv("ANYPC_IPC_TIMEOUT_MS", cls.ipc_timeout_ms)),
            max_message_bytes=int(
                os.getenv("ANYPC_MAX_MESSAGE_BYTES", cls.max_message_bytes)
            ),
        )
