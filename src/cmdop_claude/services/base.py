"""Base service."""
from abc import ABC
from .._config import Config

class BaseService(ABC):
    """Base class for all synchronous services."""
    
    __slots__ = ("_config",)
    
    def __init__(self, config: Config) -> None:
        self._config = config

class AsyncBaseService(ABC):
    """Base class for all asynchronous services."""
    
    __slots__ = ("_config",)
    
    def __init__(self, config: Config) -> None:
        self._config = config
