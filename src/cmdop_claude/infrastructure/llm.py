"""LLMCaller — thin wrapper over SDKRouter.parse() with structured output."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Generic, Optional, Type, TypeVar

from pydantic import BaseModel

if TYPE_CHECKING:
    from sdkrouter import SDKRouter

T = TypeVar("T", bound=BaseModel)


@dataclass
class LLMResult(Generic[T]):
    parsed: Optional[T]
    tokens: int

    @property
    def has_content(self) -> bool:
        return self.parsed is not None


class LLMCaller:
    """Wraps SDKRouter.parse() — call once, get (parsed, tokens) back.

    parsed may be None if the LLM returned no structured content.
    Always check result.has_content or result.parsed is not None before use.
    """

    def __init__(self, sdk: "SDKRouter") -> None:
        self._sdk = sdk

    def call(
        self,
        model: Any,
        messages: list[dict],
        response_format: Type[T],
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> LLMResult[T]:
        response = self._sdk.parse(
            model=model,
            messages=messages,
            response_format=response_format,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        tokens = response.usage.total_tokens if response.usage else 0
        parsed: Optional[T] = response.choices[0].message.parsed
        return LLMResult(parsed=parsed, tokens=tokens)
