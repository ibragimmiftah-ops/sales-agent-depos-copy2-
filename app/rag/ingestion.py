"""Knowledge base ingestion into the vector store."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger
from app.rag.vector_store import get_vector_store

logger = get_logger(__name__)

DEFAULT_CHUNK_SIZE = 800
DEFAULT_CHUNK_OVERLAP = 100


def _chunk_text(text: str, chunk_size: int = DEFAULT_CHUNK_SIZE, overlap: int = DEFAULT_CHUNK_OVERLAP) -> list[str]:
    """Simple sliding-window chunker preserving paragraph boundaries when possible."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        if len(current) + len(paragraph) + 2 <= chunk_size:
            current = f"{current}\n\n{paragraph}".strip() if current else paragraph
        else:
            if current:
                chunks.append(current)
            # If a single paragraph exceeds chunk_size, split it hard.
            if len(paragraph) > chunk_size:
                for i in range(0, len(paragraph), chunk_size - overlap):
                    chunks.append(paragraph[i : i + chunk_size])
                current = ""
            else:
                current = paragraph

    if current:
        chunks.append(current)
    return chunks


def load_kb_documents(kb_dir: str | None = None) -> list[dict[str, Any]]:
    """Load markdown files from the knowledge base directory."""
    directory = Path(kb_dir or settings.KNOWLEDGE_BASE_DIR)
    documents: list[dict[str, Any]] = []

    for path in sorted(directory.glob("*.md")):
        category = path.stem
        text = path.read_text(encoding="utf-8")
        chunks = _chunk_text(text)
        for idx, chunk in enumerate(chunks):
            documents.append(
                {
                    "id": f"{category}_{idx}",
                    "content": chunk,
                    "metadata": {
                        "source": path.name,
                        "category": category,
                        "chunk_index": idx,
                    },
                }
            )

    logger.info("kb_documents_loaded", count=len(documents), files=len(list(directory.glob("*.md"))))
    return documents


async def ingest_knowledge_base(kb_dir: str | None = None) -> int:
    """Ingest all KB documents into the configured vector store."""
    store = get_vector_store()
    documents = load_kb_documents(kb_dir)
    await store.ingest(documents)
    logger.info("knowledge_base_ingested", count=len(documents))
    return len(documents)


if __name__ == "__main__":
    count = asyncio.run(ingest_knowledge_base())
    print(f"Ingested {count} chunks")
