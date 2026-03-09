"""Embedding service — wraps provider API to produce float vectors."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cmdop_claude.models.config.cmdop_config import LLMRouting

logger = logging.getLogger(__name__)

# Embedding model per routing mode.
# openrouter supports /api/v1/embeddings with openai-compatible models.
_EMBED_MODEL: dict[str, str] = {
    "openai": "text-embedding-3-small",
    "openrouter": "openai/text-embedding-3-small",
    "sdkrouter": "openai/text-embedding-3-small",
}

EMBED_DIMS = 1536  # text-embedding-3-small dimensions
EMBED_BATCH_SIZE = 100  # max texts per API call


class EmbedService:
    """Thin wrapper — embeds texts using the configured provider directly."""

    def __init__(self, routing: LLMRouting) -> None:
        self._routing = routing
        self._model = _EMBED_MODEL.get(routing.mode, "openai/text-embedding-3-small")
        self._client = self._build_client()

    def _build_client(self):
        from sdkrouter import SDKRouter
        routing = self._routing
        # use_self_hosted=False + explicit llm_url= routes LLM/embeddings directly
        # to the provider URL; api_url stays on api.sdkrouter.com for other tools.
        return SDKRouter(
            api_key=routing.api_key or "no-key",
            llm_url=routing.resolved_base_url,
            use_self_hosted=False,
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts. Returns list of float vectors."""
        if not texts:
            return []
        result: list[list[float]] = []
        for i in range(0, len(texts), EMBED_BATCH_SIZE):
            batch = texts[i:i + EMBED_BATCH_SIZE]
            try:
                resp = self._client.embeddings.create(batch, model=self._model)
                ordered = sorted(resp.data, key=lambda d: d.index)
                result.extend(d.embedding for d in ordered)
            except Exception as e:
                logger.error("Embedding batch %d-%d failed: %s", i, i + len(batch), e)
                raise
        return result

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]
