"""Vector store backends: Qdrant, ChromaDB, and keyword fallback."""

from __future__ import annotations

import asyncio
import re
from abc import ABC, abstractmethod
from typing import Any, TypedDict

from app.core.config import settings
from app.core.logging import get_logger
from app.rag.embeddings import Embedder, OpenAIEmbedder

logger = get_logger(__name__)


class SearchResult(TypedDict):
    content: str
    source: str
    category: str
    score: float


class VectorStore(ABC):
    """Abstract vector store."""

    @abstractmethod
    async def ingest(self, documents: list[dict[str, Any]]) -> None:
        """Store documents with metadata."""
        ...

    @abstractmethod
    async def search(
        self,
        query: str,
        category: str | None = None,
        top_k: int = 5,
    ) -> list[SearchResult]:
        ...


class QdrantVectorStore(VectorStore):
    """Async Qdrant vector store."""

    def __init__(
        self,
        url: str,
        collection_name: str,
        embedder: OpenAIEmbedder,
    ):
        try:
            from qdrant_client import AsyncQdrantClient
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("qdrant-client is required for Qdrant store") from exc

        self.client = AsyncQdrantClient(url=url)
        self.collection_name = collection_name
        self.embedder = embedder
        self._vector_size: int | None = None

    async def _ensure_collection(self) -> int:
        from qdrant_client.models import Distance, VectorParams

        if self._vector_size is not None:
            return self._vector_size

        # Probe vector size with a dummy embedding.
        vectors = await self.embedder.embed(["probe"])
        self._vector_size = len(vectors[0])

        exists = await self.client.collection_exists(self.collection_name)
        if not exists:
            await self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self._vector_size,
                    distance=Distance.COSINE,
                ),
            )
        return self._vector_size

    async def ingest(self, documents: list[dict[str, Any]]) -> None:
        from qdrant_client.models import PointStruct

        await self._ensure_collection()
        if not documents:
            return

        texts = [doc["content"] for doc in documents]
        vectors = await self.embedder.embed(texts)

        points = []
        for doc, vector in zip(documents, vectors):
            points.append(
                PointStruct(
                    id=doc["id"],
                    vector=vector,
                    payload={
                        "content": doc["content"],
                        "metadata": doc["metadata"],
                    },
                )
            )
        await self.client.upsert(collection_name=self.collection_name, points=points)
        logger.info("qdrant_ingested", count=len(documents))

    async def search(
        self, query: str, category: str | None = None, top_k: int = 5
    ) -> list[SearchResult]:
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        await self._ensure_collection()
        vector = (await self.embedder.embed([query]))[0]

        query_filter = None
        if category:
            query_filter = Filter(
                must=[
                    FieldCondition(
                        key="metadata.category",
                        match=MatchValue(value=category),
                    )
                ]
            )

        results = await self.client.search(
            collection_name=self.collection_name,
            query_vector=vector,
            limit=top_k,
            query_filter=query_filter,
            with_payload=True,
        )
        return [
            SearchResult(
                content=res.payload.get("content", ""),
                source=res.payload.get("metadata", {}).get("source", ""),
                category=res.payload.get("metadata", {}).get("category", ""),
                score=res.score,
            )
            for res in results
        ]


class ChromaDBVectorStore(VectorStore):
    """ChromaDB vector store (sync client wrapped in thread)."""

    def __init__(
        self,
        persist_dir: str,
        collection_name: str,
        embedder: OpenAIEmbedder,
    ):
        try:
            import chromadb
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("chromadb is required for ChromaDB store") from exc

        self.embedder = embedder
        self.collection_name = collection_name
        self.client = chromadb.PersistentClient(path=persist_dir)
        self._collection = self.client.get_or_create_collection(name=collection_name)

    async def ingest(self, documents: list[dict[str, Any]]) -> None:
        if not documents:
            return
        texts = [doc["content"] for doc in documents]
        vectors = await self.embedder.embed(texts)
        ids = [doc["id"] for doc in documents]
        metadatas = [doc["metadata"] for doc in documents]
        await asyncio.to_thread(
            self._collection.add,
            ids=ids,
            documents=texts,
            metadatas=metadatas,
            embeddings=vectors,
        )
        logger.info("chroma_ingested", count=len(documents))

    async def search(
        self, query: str, category: str | None = None, top_k: int = 5
    ) -> list[SearchResult]:
        vector = (await self.embedder.embed([query]))[0]
        where = {"category": category} if category else None
        response = await asyncio.to_thread(
            self._collection.query,
            query_embeddings=[vector],
            n_results=top_k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        results: list[SearchResult] = []
        for i, doc in enumerate(response["documents"][0]):
            distance = response["distances"][0][i]
            metadata = response["metadatas"][0][i]
            # Chroma returns L2 distance by default; convert roughly to similarity.
            score = max(0.0, 1.0 - distance)
            results.append(
                SearchResult(
                    content=doc,
                    source=metadata.get("source", ""),
                    category=metadata.get("category", ""),
                    score=score,
                )
            )
        return results


class InMemoryKeywordVectorStore(VectorStore):
    """Keyword-overlap fallback store. No API key required."""

    def __init__(self) -> None:
        self.documents: list[dict[str, Any]] = []

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return set(re.findall(r"[a-zа-я0-9]+", text.lower()))

    async def ingest(self, documents: list[dict[str, Any]]) -> None:
        self.documents.extend(documents)

    async def search(
        self, query: str, category: str | None = None, top_k: int = 5
    ) -> list[SearchResult]:
        query_tokens = self._tokens(query)
        if not query_tokens:
            return []

        scored: list[tuple[float, dict[str, Any]]] = []
        for doc in self.documents:
            if category and doc["metadata"].get("category") != category:
                continue
            doc_tokens = self._tokens(doc["content"])
            if not doc_tokens:
                continue
            overlap = len(query_tokens & doc_tokens) / len(query_tokens)
            scored.append((overlap, doc))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            SearchResult(
                content=doc["content"],
                source=doc["metadata"].get("source", ""),
                category=doc["metadata"].get("category", ""),
                score=score,
            )
            for score, doc in scored[:top_k]
            if score > 0
        ]


def get_vector_store(embedder: Embedder | None = None) -> VectorStore:
    """Factory resolving the configured vector store.

    Falls back to InMemoryKeywordVectorStore when no API key is available.
    """
    provider = settings.VECTOR_STORE_PROVIDER.lower()

    if settings.EMBEDDING_PROVIDER == "keyword":
        logger.info("vector_store_keyword_fallback")
        return InMemoryKeywordVectorStore()

    if embedder is None:
        embedder = OpenAIEmbedder()

    if provider == "qdrant":
        return QdrantVectorStore(
            url=settings.QDRANT_URL,
            collection_name=settings.QDRANT_COLLECTION_NAME,
            embedder=embedder,
        )
    if provider == "chroma":
        return ChromaDBVectorStore(
            persist_dir=settings.CHROMA_PERSIST_DIR,
            collection_name=settings.QDRANT_COLLECTION_NAME,
            embedder=embedder,
        )

    raise ValueError(f"Unknown vector store provider: {provider}")
