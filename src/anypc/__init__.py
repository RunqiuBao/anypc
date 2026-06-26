"""anypc — WebSocket gateway relaying observations to an inference process over ZeroMQ."""

from .config import Settings
from .server import InferenceServer

__all__ = ["Settings", "InferenceServer"]
__version__ = "0.1.0"
