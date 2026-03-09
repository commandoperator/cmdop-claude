"""Unit tests for EmbedService (SDKRouter mocked)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from cmdop_claude.models.config.cmdop_config import LLMRouting
from cmdop_claude.services.docs.embed_service import EMBED_BATCH_SIZE, EmbedService


def _routing(mode: str = "sdkrouter", api_key: str = "test-key") -> LLMRouting:
    return LLMRouting.model_validate({"mode": mode, "apiKey": api_key})


def _mock_embed_response(n: int, dims: int = 4) -> MagicMock:
    """Build a fake embeddings.create() response with n vectors."""
    resp = MagicMock()
    resp.data = [
        MagicMock(index=i, embedding=[float(i)] * dims) for i in range(n)
    ]
    return resp


def _make_svc(mode: str = "sdkrouter", mock_client: MagicMock | None = None) -> tuple[EmbedService, MagicMock]:
    """Create EmbedService with mocked SDKRouter, returning (svc, mock_client)."""
    client = mock_client or MagicMock()
    with patch("sdkrouter.SDKRouter", return_value=client):
        with patch("sdkrouter._constants.DEFAULT_LLM_URL", "https://llm.sdkrouter.com/v1"):
            svc = EmbedService(_routing(mode))
    return svc, client


# ── construction ──────────────────────────────────────────────────────────────


def test_model_selection_sdkrouter():
    svc, _ = _make_svc("sdkrouter")
    assert svc._model == "openai/text-embedding-3-small"


def test_model_selection_openai():
    svc, _ = _make_svc("openai")
    assert svc._model == "text-embedding-3-small"


def test_model_selection_openrouter():
    """openrouter mode uses openai-compatible model via openrouter.ai/api/v1/embeddings."""
    svc, _ = _make_svc("openrouter")
    assert svc._model == "openai/text-embedding-3-small"


def test_openrouter_uses_openrouter_url():
    """openrouter mode routes directly to openrouter.ai."""
    with patch("sdkrouter.SDKRouter") as mock_cls:
        EmbedService(_routing("openrouter"))
    call_kwargs = mock_cls.call_args[1]
    assert "openrouter.ai" in call_kwargs.get("llm_url", "")


# ── embed ─────────────────────────────────────────────────────────────────────


def test_embed_empty_returns_empty():
    svc, _ = _make_svc()
    result = svc.embed([])
    assert result == []


def test_embed_single_text():
    svc, client = _make_svc()
    client.embeddings.create.return_value = _mock_embed_response(1, dims=3)
    result = svc.embed(["hello"])

    assert len(result) == 1
    assert result[0] == [0.0, 0.0, 0.0]


def test_embed_multiple_texts():
    svc, client = _make_svc()
    client.embeddings.create.return_value = _mock_embed_response(3, dims=2)
    result = svc.embed(["a", "b", "c"])

    assert len(result) == 3
    assert result[1] == [1.0, 1.0]


def test_embed_batches_large_input():
    """Texts > EMBED_BATCH_SIZE split across multiple API calls."""
    n = EMBED_BATCH_SIZE + 5
    texts = [f"text{i}" for i in range(n)]

    def side_effect(batch, model):
        size = len(batch)
        resp = MagicMock()
        resp.data = [MagicMock(index=i, embedding=[0.0]) for i in range(size)]
        return resp

    svc, client = _make_svc()
    client.embeddings.create.side_effect = side_effect
    result = svc.embed(texts)

    assert len(result) == n
    assert client.embeddings.create.call_count == 2


def test_embed_propagates_api_error():
    svc, client = _make_svc()
    client.embeddings.create.side_effect = RuntimeError("API down")

    with pytest.raises(RuntimeError, match="API down"):
        svc.embed(["text"])


# ── embed_one ─────────────────────────────────────────────────────────────────


def test_embed_one_returns_single_vector():
    svc, client = _make_svc()
    client.embeddings.create.return_value = _mock_embed_response(1, dims=5)
    vec = svc.embed_one("query")

    assert isinstance(vec, list)
    assert len(vec) == 5
