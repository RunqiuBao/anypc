"""Example inference backend — the `anypc-example-worker` executable.

A minimal REP server that consumes observations from the gateway and returns a
stub reply. Requests and replies are msgpack (with numpy support), matching the
gateway and openpi's remote-inference wire format. Replace `run_inference` with
a real model call, or use this as a reference for wiring your own inference
process to the ZeroMQ socket.
"""

from __future__ import annotations

import argparse
from typing import Any

import numpy as np
import zmq

from .config import DEFAULT_IPC_ENDPOINT
from .openpi_client import msgpack_numpy


def run_inference(obs: dict[str, Any]) -> dict[str, Any]:
    """Stub: echo back a summary of the observation. Swap in a real model here.

    `obs` is the unpacked observation dict. With openpi-style clients it
    typically holds numpy arrays (e.g. ``obs["image"]``) plus a ``prompt``.
    """
    image = obs.get("image")
    image_shape = list(image.shape) if isinstance(image, np.ndarray) else None
    return {
        "ok": True,
        "prompt": obs.get("prompt"),
        "image_shape": image_shape,
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
            payload = sock.recv()
            try:
                obs = msgpack_numpy.unpackb(payload)
                result = run_inference(obs)
            except Exception as exc:  # never leave a REQ peer hanging
                result = {"ok": False, "error": str(exc)}
            sock.send(msgpack_numpy.packb(result))
    except KeyboardInterrupt:
        print("\n[worker] shutting down", flush=True)
    finally:
        sock.close(linger=0)


if __name__ == "__main__":
    main()
