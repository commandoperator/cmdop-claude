"""Infrastructure layer — thin wrappers over external I/O."""
from .llm import LLMCaller, LLMResult
from .storage import JSONStorage

__all__ = ["LLMCaller", "LLMResult", "JSONStorage"]
