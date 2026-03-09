"""Embedding service — wraps provider API to produce float vectors."""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
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
EMBED_CONCURRENCY = 8   # parallel batch requests


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
            timeout=120.0,
        )

    def _embed_batch(self, batch: list[str]) -> list[list[float]]:
        resp = self._client.embeddings.create(batch, model=self._model)
        ordered = sorted(resp.data, key=lambda d: d.index)
        return [d.embedding for d in ordered]

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts in parallel batches. Returns list of float vectors in input order."""
        if not texts:
            return []

        batches = [
            texts[i:i + EMBED_BATCH_SIZE]
            for i in range(0, len(texts), EMBED_BATCH_SIZE)
        ]

        results: list[list[list[float]] | None] = [None] * len(batches)

        with ThreadPoolExecutor(max_workers=EMBED_CONCURRENCY) as pool:
            future_to_idx = {
                pool.submit(self._embed_batch, batch): idx
                for idx, batch in enumerate(batches)
            }
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                offset = idx * EMBED_BATCH_SIZE
                try:
                    results[idx] = future.result()
                except Exception as e:
                    logger.error(
                        "Embedding batch %d-%d failed: %s",
                        offset, offset + len(batches[idx]), e,
                    )
                    raise

        return [emb for batch_result in results for emb in (batch_result or [])]

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]
