"""
Corpus-agnostic quality-gate helpers for anyone writing into a shared RAG
corpus. Built originally for agents-training/'s store_building_patterns loop
(pipeline.py) and generalized here so a second real writer (Nova, promoting
lessons into "playbook" — see src/org/executor.py) reuses the same tier-1
logic instead of a second, independently-drifting copy.
"""
from __future__ import annotations


def passes_sanity_check(text: str) -> tuple[bool, str]:
    """Cheap, deterministic, no-LLM-call gate. Rejects the obviously-broken
    cases: empty/near-empty fragments, and suspiciously long "lessons" that
    read more like leaked prose than a concise structural/practice principle."""
    words = text.split()
    if len(text.strip()) < 15:
        return False, "too short to be a real principle"
    if len(words) > 45:
        return False, "too long — reads like prose, not a concise lesson"
    if text.count("!") >= 2 or text.count("$") >= 2:
        return False, "reads like ad copy, not a structural/practice observation"
    return True, ""


async def is_new_entry(corpus: str, text: str, threshold: float = 0.90) -> bool:
    """True if nothing already in `corpus` is a near-duplicate of `text`
    (cosine similarity >= threshold), so a reworded repeat doesn't pile up."""
    from src.rag.index import search
    hits = await search(corpus, text, top_k=1)
    if not hits:
        return True
    score = hits[0].get("score")
    return score is None or score < threshold
