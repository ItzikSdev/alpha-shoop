"""
Thin redisvl wrapper — two RAG corpora sharing one upsert/search code path.

Corpora:
  - "cj_catalog": CJ Dropshipping product candidates Sol has seen/evaluated
    (accepted, rejected, or pending), so Sol can check "have I looked at this
    before" and recall why a product was rejected.
  - "playbook": internal markdown docs/guides that explain how Sol should
    source, describe, and display products (fed by
    `scripts/ingest_playbook.py`).

Both corpora are separate redisvl `SearchIndex` objects (own key prefix, own
schema) but go through the same `upsert()` / `search()` functions here.
Embeddings come from `src.embeddings.embed_text` (local Ollama — no external
API key). Matches this codebase's fail-soft style: any Redis/connection
error is logged as a warning and results in `False` / `[]`, never a raise.
"""
from __future__ import annotations

import logging
from typing import Any

from redisvl.index import AsyncSearchIndex
from redisvl.query import VectorQuery
from redisvl.query.filter import FilterExpression, Tag, Text
from redisvl.redis.utils import array_to_buffer
from redisvl.schema import IndexSchema

from src.config import get_settings
from src.embeddings import embed_text

logger = logging.getLogger(__name__)

VECTOR_FIELD_NAME = "vector"
_VECTOR_DTYPE = "float32"

# Corpus schemas, keyed by corpus name. `fields` describes the extra
# metadata fields (beyond the always-present "text" field holding the
# embedded/original text body) each corpus indexes for filtering/recall.
# Field "type" is either "tag" (exact-match filtering) or "text" (full-text,
# also usable for filtering, and used for fields that are informational only
# like "images"/"variants" JSON blobs).
_CORPUS_SCHEMAS: dict[str, dict[str, Any]] = {
    "cj_catalog": {
        "prefix": "cj_catalog",
        "fields": [
            {"name": "pid", "type": "tag"},
            {"name": "verdict", "type": "tag"},
            {"name": "reason", "type": "text"},
            {"name": "category", "type": "text"},
            {"name": "images", "type": "text"},
            {"name": "variants", "type": "text"},
        ],
    },
    "playbook": {
        "prefix": "playbook",
        "fields": [
            {"name": "source_path", "type": "tag"},
            {"name": "doc_title", "type": "text"},
            {"name": "section", "type": "text"},
        ],
    },
}

# Cache of created/connected AsyncSearchIndex objects, one per corpus.
_indices: dict[str, AsyncSearchIndex] = {}


def _field_type(corpus: str, field_name: str) -> str | None:
    for field in _CORPUS_SCHEMAS[corpus]["fields"]:
        if field["name"] == field_name:
            return field["type"]
    return None


def _build_schema(corpus: str, dims: int) -> IndexSchema:
    cfg = _CORPUS_SCHEMAS[corpus]
    fields: list[dict[str, Any]] = [{"name": "text", "type": "text"}]
    fields.extend(cfg["fields"])
    fields.append(
        {
            "name": VECTOR_FIELD_NAME,
            "type": "vector",
            "attrs": {
                "algorithm": "hnsw",
                "dims": dims,
                "distance_metric": "cosine",
                "datatype": _VECTOR_DTYPE.upper(),
            },
        }
    )
    return IndexSchema.from_dict(
        {
            "index": {
                "name": corpus,
                "prefix": cfg["prefix"],
                "storage_type": "hash",
            },
            "fields": fields,
        }
    )


async def _get_index(corpus: str, dims: int) -> AsyncSearchIndex:
    """Return the (cached) redisvl index for `corpus`, creating it in Redis
    on first use. `dims` comes from the embedding model's actual output size,
    so the index always matches whatever `embed_text()` produces."""
    if corpus not in _indices:
        settings = get_settings()
        schema = _build_schema(corpus, dims)
        _indices[corpus] = AsyncSearchIndex(schema, redis_url=settings.redis_url)

    index = _indices[corpus]
    if not await index.exists():
        await index.create()
    return index


def _return_fields(corpus: str) -> list[str]:
    return ["text"] + [f["name"] for f in _CORPUS_SCHEMAS[corpus]["fields"]]


async def upsert(corpus: str, doc_id: str, text: str, metadata: dict) -> bool:
    """Embed `text` and upsert it (+ metadata) into the given corpus's Redis
    index, keyed by `doc_id`. Creates the index lazily on first call. Returns
    False (logging a warning) on any embedding/connection/index error."""
    if corpus not in _CORPUS_SCHEMAS:
        logger.warning("Unknown RAG corpus %r, skipping upsert", corpus)
        return False
    if not text.strip():
        return False

    vector = await embed_text(text)
    if vector is None:
        return False

    try:
        index = await _get_index(corpus, dims=len(vector))
        payload: dict[str, Any] = {
            "text": text,
            VECTOR_FIELD_NAME: array_to_buffer(vector, _VECTOR_DTYPE),
        }
        for field in _CORPUS_SCHEMAS[corpus]["fields"]:
            value = metadata.get(field["name"])
            if value is not None:
                payload[field["name"]] = str(value)
        await index.load([payload], keys=[index.key(doc_id)])
        return True
    except Exception as exc:
        logger.warning("RAG upsert failed corpus=%s doc_id=%s: %s", corpus, doc_id, exc)
        return False


async def list_all(corpus: str, limit: int = 200) -> list[dict]:
    """Raw listing of every doc in `corpus` (metadata only, never the vector
    bytes) — for a human-facing browse view (the dashboard's RAG page), not
    semantic search. Fails soft like upsert()/search()."""
    if corpus not in _CORPUS_SCHEMAS:
        logger.warning("Unknown RAG corpus %r, skipping list_all", corpus)
        return []

    import redis.asyncio as aredis

    settings = get_settings()
    prefix = f"{_CORPUS_SCHEMAS[corpus]['prefix']}:"
    # Explicit field list — never "vector" (binary bytes; HGETALL would try to
    # UTF-8-decode it via decode_responses=True and crash).
    field_names = ["text"] + [f["name"] for f in _CORPUS_SCHEMAS[corpus]["fields"]]
    out: list[dict] = []
    client = aredis.from_url(settings.redis_url, decode_responses=True)
    try:
        async for key in client.scan_iter(match=f"{prefix}*", count=100):
            if len(out) >= limit:
                break
            values = await client.hmget(key, field_names)
            entry: dict[str, Any] = {"id": key[len(prefix):]}
            for name, value in zip(field_names, values):
                if value is not None:
                    entry[name] = value
            out.append(entry)
    except Exception as exc:
        logger.warning("RAG list_all failed corpus=%s: %s", corpus, exc)
        return []
    finally:
        await client.aclose()
    return out


def _build_filter(corpus: str, filters: dict) -> FilterExpression | None:
    expr: FilterExpression | None = None
    for field_name, value in filters.items():
        field_type = _field_type(corpus, field_name)
        if field_type == "tag":
            clause = Tag(field_name) == str(value)
        else:
            # Default to a text-equality clause for unknown/text fields —
            # still a valid filter even if the field isn't in the schema
            # (Redis just won't match anything for a bogus field name).
            clause = Text(field_name) == str(value)
        expr = clause if expr is None else (expr & clause)
    return expr


async def search(
    corpus: str,
    query: str,
    filters: dict | None = None,
    top_k: int = 5,
) -> list[dict]:
    """Embed `query` and run a vector similarity search over `corpus`,
    optionally narrowed by an exact-match `filters` dict (hybrid search).
    Returns [{"id": ..., "text": ..., "score": ..., **metadata}, ...] best
    match first. Fails soft: returns [] and logs a warning on any error
    (including "index/corpus doesn't exist yet")."""
    if corpus not in _CORPUS_SCHEMAS:
        logger.warning("Unknown RAG corpus %r, skipping search", corpus)
        return []

    vector = await embed_text(query)
    if vector is None:
        return []

    try:
        index = await _get_index(corpus, dims=len(vector))
        filter_expression = _build_filter(corpus, filters) if filters else None
        vector_query = VectorQuery(
            vector=vector,
            vector_field_name=VECTOR_FIELD_NAME,
            return_fields=_return_fields(corpus),
            filter_expression=filter_expression,
            num_results=top_k,
        )
        results = await index.query(vector_query)
    except Exception as exc:
        logger.warning("RAG search failed corpus=%s query=%r: %s", corpus, query, exc)
        return []

    prefix = f"{_CORPUS_SCHEMAS[corpus]['prefix']}:"
    out: list[dict] = []
    for doc in results:
        doc_id = doc.get("id", "")
        if doc_id.startswith(prefix):
            doc_id = doc_id[len(prefix):]
        distance = doc.get("vector_distance")
        entry: dict[str, Any] = {
            "id": doc_id,
            "text": doc.get("text", ""),
            "score": 1.0 - float(distance) if distance is not None else None,
        }
        for field in _CORPUS_SCHEMAS[corpus]["fields"]:
            if field["name"] in doc:
                entry[field["name"]] = doc[field["name"]]
        out.append(entry)
    return out
