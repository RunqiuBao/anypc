"""Example inference backend — the `anypc-example-worker` executable.

A minimal REP server that consumes requests from the gateway and returns a
stub reply. Replace `run_inference` with a real model call, or use this as a
reference for wiring your own inference process to the ZeroMQ socket.
"""

from __future__ import annotations

import argparse
import json
from typing import Any

import zmq

from .config import DEFAULT_IPC_ENDPOINT


def run_inference(metadata: dict[str, Any], image: bytes) -> dict[str, Any]:
    """Stub: echo back what was received. Swap in a real model here."""
    return {
        "ok": True,
        "prompt": metadata.get("prompt"),
        "received_bytes": len(image),
        "filename": metadata.get("filename"),
        "result": "stub-response",
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="anypc-example-worker",
        description="Example ZeroMQ inference backend for the anypc gateway.",
    )
    parser.add_argument(
        "--ipc-endpoint",
        default=DEFAULT_IPC_ENDPOINT,
        help="ZeroMQ endpoint to bind (must match the gateway)",
    )
    args = parser.parse_args(argv)

    ctx = zmq.Context.instance()
    sock = ctx.socket(zmq.REP)
    sock.bind(args.ipc_endpoint)
    print(f"[worker] listening on {args.ipc_endpoint}", flush=True)

    try:
        while True:
            frames = sock.recv_multipart()
            metadata = json.loads(frames[0].decode("utf-8")) if frames else {}
            image = frames[1] if len(frames) > 1 else b""
            try:
                result = run_inference(metadata, image)
            except Exception as exc:  # never leave a REQ peer hanging
                result = {"ok": False, "error": str(exc)}
            sock.send_multipart([json.dumps(result).encode("utf-8")])
    except KeyboardInterrupt:
        print("\n[worker] shutting down", flush=True)
    finally:
        sock.close(linger=0)


if __name__ == "__main__":
    main()
