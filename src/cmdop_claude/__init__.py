"""Claude Control Plane package."""
from ._config import Config, configure, get_config
from ._client import Client

__all__ = [
    "Config",
    "configure",
    "get_config",
    "Client",
]

try:
    from importlib.metadata import version
    __version__ = version("cmdop-claude")
except Exception:
    __version__ = "unknown"
