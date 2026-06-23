"""
Store knowledge embeddings — local Ollama embeddings + ChromaDB vector store.

Each store's description (free text: what it contains today + what it should
become) is embedded and upserted into a per-store ChromaDB collection. Agents
query this via `query_store_knowledge()` for agentic RAG — e.g. the director
or ecommerce_manager asking "what categories should this store carry?".

No external API key needed — embeddings run locally via Ollama.
"""
from __future__ import annotations

import logging

import chromadb
import httpx

from src.config import get_settings

logger = logging.getLogger(__name__)

_CHROMA_CLIENT: chromadb.ClientAPI | None = None


def _get_chroma_client() -> chromadb.ClientAPI:
    global _CHROMA_CLIENT
    if _CHROMA_CLIENT is None:
        settings = get_settings()
        _CHROMA_CLIENT = chromadb.PersistentClient(path=settings.chroma_path)
    return _CHROMA_CLIENT


async def embed_text(text: str) -> list[float] | None:
    """Generate an embedding vector for text via the local Ollama model."""
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{settings.ollama_url}/api/embeddings",
                json={"model": settings.ollama_embed_model, "prompt": text},
            )
            resp.raise_for_status()
            return resp.json().get("embedding")
    except Exception as exc:
        logger.warning("Ollama embedding failed: %s", exc)
        return None


_COLLECTION_NAME = "store_knowledge"


def _collection():
    client = _get_chroma_client()
    return client.get_or_create_collection(_COLLECTION_NAME)


async def upsert_store_knowledge(store_id: str, description: str, metadata: dict | None = None) -> bool:
    """Embed a store's description and upsert it into the vector store, keyed by store_id."""
    if not description.strip():
        return False
    vector = await embed_text(description)
    if vector is None:
        return False
    meta = {**(metadata or {}), "store_id": store_id}
    try:
        _collection().upsert(
            ids=[store_id],
            embeddings=[vector],
            documents=[description],
            metadatas=[meta],
        )
        return True
    except Exception as exc:
        logger.warning("Chroma upsert failed for store %s: %s", store_id, exc)
        return False


async def query_store_knowledge(query: str, store_id: str | None = None, top_k: int = 3) -> list[dict]:
    """
    Agentic RAG entry point — semantic search over store descriptions.

    If store_id is given, restricts results to that store (still useful to pull
    back the stored description's most relevant framing for a specific question).
    Otherwise searches across all stores' knowledge.

    Returns: [{"store_id": ..., "document": ..., "distance": ...}, ...]
    """
    vector = await embed_text(query)
    if vector is None:
        return []
    try:
        where = {"store_id": store_id} if store_id else None
        result = _collection().query(query_embeddings=[vector], n_results=top_k, where=where)
    except Exception as exc:
        logger.warning("Chroma query failed: %s", exc)
        return []

    ids = result.get("ids", [[]])[0]
    docs = result.get("documents", [[]])[0]
    distances = result.get("distances", [[]])[0]
    return [
        {"store_id": ids[i], "document": docs[i], "distance": distances[i]}
        for i in range(len(ids))
    ]


def delete_store_knowledge(store_id: str) -> None:
    try:
        _collection().delete(ids=[store_id])
    except Exception as exc:
        logger.warning("Chroma delete failed for store %s: %s", store_id, exc)
