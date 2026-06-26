"""Entry point for the `anypc-server` executable."""

from __future__ import annotations

import argparse
import logging

from .config import Settings
from .server import InferenceServer


def main(argv: list[str] | None = None) -> None:
    defaults = Settings.from_env()

    parser = argparse.ArgumentParser(
        prog="anypc-server",
        description="Start the anypc WebSocket inference gateway.",
    )
    parser.add_argument("--host", default=defaults.host, help="bind address")
    parser.add_argument("--port", type=int, default=defaults.port, help="bind port")
    parser.add_argument(
        "--ipc-endpoint",
        default=defaults.ipc_endpoint,
        help="ZeroMQ endpoint of the inference backend",
    )
    parser.add_argument(
        "--ipc-timeout-ms",
        type=int,
        default=defaults.ipc_timeout_ms,
        help="backend reply timeout in milliseconds",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="logging level (DEBUG, INFO, WARNING, ...)",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    settings = Settings(
        host=args.host,
        port=args.port,
        ipc_endpoint=args.ipc_endpoint,
        ipc_timeout_ms=args.ipc_timeout_ms,
        max_message_bytes=defaults.max_message_bytes,
    )

    InferenceServer(settings).serve_forever()


if __name__ == "__main__":
    main()
