"""Embedding providers for RAG."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class Embedder(ABC):
    """Abstract text embedder."""

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Return a list of embedding vectors."""
        ...


class OpenAIEmbedder(Embedder):
    """OpenAI text-embedding model."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        try:
            import openai
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("openai package is required for OpenAI embeddings") from exc

        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model = model or settings.EMBEDDING_MODEL
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required for OpenAI embeddings")
        self._client = openai.AsyncOpenAI(api_key=self.api_key)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = await self._client.embeddings.create(
            model=self.model,
            input=texts,
        )
        return [item.embedding for item in response.data]


class KeywordEmbedder(Embedder):
    """Placeholder embedder for keyword-only retrieval.

    Not used by InMemoryKeywordVectorStore, but satisfies the protocol.
    """

    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError("Keyword retrieval does not use dense embeddings")


def get_embedder() -> Embedder:
    provider = settings.EMBEDDING_PROVIDER.lower()
    if provider == "openai":
        return OpenAIEmbedder()
    if provider == "keyword":
        return KeywordEmbedder()
    raise ValueError(f"Unknown embedding provider: {provider}")
