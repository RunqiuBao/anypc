"""Vendored subset of the openpi client.

This is a self-contained copy of the websocket client + helpers from
Physical Intelligence's openpi (``packages/openpi-client``, Apache-2.0), so this
repo speaks the exact same remote-inference wire format as openpi and can act as
both server (see :mod:`anypc.server`) and client without depending on the openpi
package being installed.

Upstream: https://github.com/Physical-Intelligence/openpi
Protocol: https://github.com/Physical-Intelligence/openpi/blob/main/docs/remote_inference.md
"""

from . import image_tools, msgpack_numpy, websocket_client_policy

__all__ = ["image_tools", "msgpack_numpy", "websocket_client_policy"]
