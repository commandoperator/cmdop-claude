"""Tests for LLMCaller."""
from unittest.mock import MagicMock
from pydantic import BaseModel

from cmdop_claude.infrastructure.llm import LLMCaller, LLMResult


class _MyResponse(BaseModel):
    text: str
    count: int


def _make_sdk_response(parsed_obj, total_tokens: int = 42, model: str = "test-model"):
    usage = MagicMock()
    usage.total_tokens = total_tokens
    msg = MagicMock()
    msg.parsed = parsed_obj
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.usage = usage
    resp.choices = [choice]
    resp.model = model
    return resp


def test_call_returns_parsed_and_tokens():
    sdk = MagicMock()
    parsed = _MyResponse(text="hello", count=3)
    sdk.parse.return_value = _make_sdk_response(parsed, total_tokens=100)

    caller = LLMCaller(sdk)
    result = caller.call(
        model="some-model",
        messages=[{"role": "user", "content": "hi"}],
        response_format=_MyResponse,
    )

    assert isinstance(result, LLMResult)
    assert result.parsed.text == "hello"
    assert result.parsed.count == 3
    assert result.tokens == 100


def test_call_passes_params_to_sdk():
    sdk = MagicMock()
    parsed = _MyResponse(text="x", count=0)
    sdk.parse.return_value = _make_sdk_response(parsed)

    caller = LLMCaller(sdk)
    caller.call(
        model="my-model",
        messages=[{"role": "system", "content": "sys"}, {"role": "user", "content": "u"}],
        response_format=_MyResponse,
        temperature=0.5,
        max_tokens=1024,
    )

    sdk.parse.assert_called_once_with(
        model="my-model",
        messages=[{"role": "system", "content": "sys"}, {"role": "user", "content": "u"}],
        response_format=_MyResponse,
        temperature=0.5,
        max_tokens=1024,
    )


def test_call_zero_tokens_when_usage_none():
    sdk = MagicMock()
    parsed = _MyResponse(text="x", count=0)
    resp = _make_sdk_response(parsed)
    resp.usage = None
    sdk.parse.return_value = resp

    caller = LLMCaller(sdk)
    result = caller.call(model="m", messages=[], response_format=_MyResponse)
    assert result.tokens == 0


def test_call_returns_none_parsed_when_llm_returns_none():
    sdk = MagicMock()
    resp = _make_sdk_response(None)
    sdk.parse.return_value = resp

    caller = LLMCaller(sdk)
    result = caller.call(model="m", messages=[], response_format=_MyResponse)
    assert result.parsed is None
    assert not result.has_content
