"""anypc — FastAPI gateway relaying prompts to an inference process over ZeroMQ."""

from .config import Settings
from .server import create_app

__all__ = ["Settings", "create_app"]
__version__ = "0.1.0"
