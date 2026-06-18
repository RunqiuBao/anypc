"""Entry point for the `anypc-server` executable."""

from __future__ import annotations

import argparse
import os

import uvicorn

from .config import Settings


def main(argv: list[str] | None = None) -> None:
    defaults = Settings.from_env()

    parser = argparse.ArgumentParser(
        prog="anypc-server",
        description="Start the anypc FastAPI inference gateway.",
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
        "--reload", action="store_true", help="auto-reload on code changes (dev)"
    )
    parser.add_argument(
        "--workers", type=int, default=1, help="number of uvicorn workers"
    )
    args = parser.parse_args(argv)

    # Pass config to the app factory (which reads the environment) so that it
    # also works under --reload/--workers, where uvicorn re-imports the app.
    os.environ["ANYPC_HOST"] = args.host
    os.environ["ANYPC_PORT"] = str(args.port)
    os.environ["ANYPC_IPC_ENDPOINT"] = args.ipc_endpoint
    os.environ["ANYPC_IPC_TIMEOUT_MS"] = str(args.ipc_timeout_ms)

    uvicorn.run(
        "anypc.server:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=args.workers if not args.reload else None,
    )


if __name__ == "__main__":
    main()
