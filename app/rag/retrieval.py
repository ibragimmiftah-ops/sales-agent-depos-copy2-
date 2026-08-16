"""RAG retrieval wrapper."""

from __future__ import annotations

from app.core.exceptions import RAGError
from app.core.logging import get_logger
from app.rag.vector_store import SearchResult, VectorStore, get_vector_store

logger = get_logger(__name__)


class KnowledgeRetriever:
    """High-level RAG retriever used by the knowledge tool."""

    def __init__(self, store: VectorStore | None = None):
        self.store = store or get_vector_store()

    async def search(
        self,
        query: str,
        category: str | None = None,
        top_k: int = 5,
    ) -> list[SearchResult]:
        try:
            results = await self.store.search(
                query=query,
                category=category,
                top_k=top_k,
            )
            logger.info(
                "rag_search",
                query=query,
                category=category,
                results_count=len(results),
            )
            return results
        except Exception as exc:
            logger.error("rag_search_failed", error=str(exc))
            raise RAGError(f"RAG search failed: {exc}") from exc

    async def search_to_context(self, query: str, category: str | None = None, top_k: int = 5) -> str:
        """Format top results into a single context string for the LLM."""
        results = await self.search(query, category=category, top_k=top_k)
        if not results:
            return ""
        parts = []
        for i, r in enumerate(results, 1):
            parts.append(f"[{i}] Source: {r['source']} (score: {r['score']:.2f})\n{r['content']}")
        return "\n\n".join(parts)
