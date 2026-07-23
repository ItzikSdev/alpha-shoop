"""
Ingest Sol's internal "playbook" — markdown docs/guides that explain how Sol
should source, describe, and display products — into the "playbook" RAG
corpus in Redis (see `src.rag.index`).

Walks:
  - stores/shopify/hydrogen-alphaforbaby/docs/*.md
  - stores/shopify/hydrogen-alphaforbaby/guides/**/*.md
  - any SKILL.md under stores/shopify/hydrogen-alphaforbaby/.claude/skills/ or
    the repo-root .claude/skills/ (if those directories exist)

Each file is split into chunks by markdown "##" (h2) headings — any content
before the first h2 becomes its own "intro" chunk, and a file with no h2
headings at all becomes a single whole-file chunk. Chunks over ~2000 chars
are split further on paragraph boundaries. Each chunk is upserted with
doc_id = f"{relative_path}#{section_slug}" (or "...#slug-2", "...#slug-3", ...
for paragraph-split overflow chunks of one section), so re-running this
script is idempotent — same doc_id just overwrites the old vector/metadata.

Usage (from repo root):
    python -m scripts.ingest_playbook
    python scripts/ingest_playbook.py
"""
from __future__ import annotations

import asyncio
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.rag.index import upsert  # noqa: E402

MAX_CHUNK_CHARS = 2000

_H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
_H2_SPLIT_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "section"


@dataclass
class Chunk:
    section: str
    text: str


def _split_sections(content: str, doc_title: str) -> list[Chunk]:
    """Split markdown content into (heading, body) chunks by h2 headings.
    Content before the first h2 becomes an "intro" chunk (if non-empty).
    Falls back to the whole file as one chunk if there are no h2 headings."""
    matches = list(_H2_SPLIT_RE.finditer(content))
    if not matches:
        return [Chunk(section=doc_title, text=content.strip())]

    chunks: list[Chunk] = []

    preamble = content[: matches[0].start()].strip()
    if preamble:
        chunks.append(Chunk(section="Intro", text=preamble))

    for i, match in enumerate(matches):
        heading = match.group(1).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        body = content[start:end].strip()
        chunks.append(Chunk(section=heading, text=f"## {heading}\n\n{body}" if body else f"## {heading}"))

    return chunks


def _split_paragraphs(text: str, max_chars: int) -> list[str]:
    """Split a chunk further on blank-line paragraph boundaries if it's over
    max_chars, greedily packing paragraphs into ~max_chars-sized pieces. Any
    resulting piece still over max_chars (e.g. a "one line per entry"
    changelog with no blank lines) is further packed by single newlines, and
    as a last resort hard-sliced by character count so no single embed call
    ever gets an unbounded blob."""
    if len(text) <= max_chars:
        return [text]

    paragraphs = re.split(r"\n\s*\n", text)
    pieces = _pack(paragraphs, max_chars, sep="\n\n")

    packed: list[str] = []
    for piece in pieces:
        if len(piece) <= max_chars:
            packed.append(piece)
            continue
        lines = piece.split("\n")
        for sub in _pack(lines, max_chars, sep="\n"):
            if len(sub) <= max_chars:
                packed.append(sub)
            else:
                # A single line longer than max_chars — hard-slice it.
                packed.extend(sub[i : i + max_chars] for i in range(0, len(sub), max_chars))
    return packed or [text]


def _pack(parts: list[str], max_chars: int, sep: str) -> list[str]:
    """Greedily pack `parts` into ~max_chars-sized pieces, joined by `sep`."""
    pieces: list[str] = []
    current = ""
    for part in parts:
        candidate = f"{current}{sep}{part}" if current else part
        if len(candidate) > max_chars and current:
            pieces.append(current)
            current = part
        else:
            current = candidate
    if current:
        pieces.append(current)
    return pieces


def _doc_title(content: str, fallback: str) -> str:
    match = _H1_RE.search(content)
    return match.group(1).strip() if match else fallback


def _find_markdown_files() -> list[Path]:
    candidates: list[Path] = []

    hydrogen_root = REPO_ROOT / "stores" / "shopify" / "hydrogen-alphaforbaby"
    docs_dir = hydrogen_root / "docs"
    guides_dir = hydrogen_root / "guides"

    if docs_dir.is_dir():
        candidates.extend(sorted(docs_dir.glob("*.md")))
    if guides_dir.is_dir():
        candidates.extend(sorted(guides_dir.glob("**/*.md")))

    # Additional design/architecture docs kept outside the per-store docs/ tree.
    disagin_dir = REPO_ROOT / "stores" / "disagin"
    if disagin_dir.is_dir():
        candidates.extend(sorted(disagin_dir.glob("**/*.md")))

    for skills_dir in (
        hydrogen_root / ".claude" / "skills",
        REPO_ROOT / ".claude" / "skills",
    ):
        if skills_dir.is_dir():
            candidates.extend(sorted(skills_dir.glob("**/SKILL.md")))

    # De-dup while preserving order (in case any glob overlaps).
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in candidates:
        if path not in seen:
            seen.add(path)
            unique.append(path)
    return unique


async def _ingest_file(path: Path) -> int:
    content = path.read_text(encoding="utf-8")
    relative_path = str(path.relative_to(REPO_ROOT))
    doc_title = _doc_title(content, fallback=path.stem)

    ingested = 0
    for chunk in _split_sections(content, doc_title):
        pieces = _split_paragraphs(chunk.text, MAX_CHUNK_CHARS)
        base_slug = _slugify(chunk.section)
        for i, piece in enumerate(pieces):
            if not piece.strip():
                continue
            slug = base_slug if i == 0 else f"{base_slug}-{i + 1}"
            doc_id = f"{relative_path}#{slug}"
            ok = await upsert(
                "playbook",
                doc_id=doc_id,
                text=piece,
                metadata={
                    "source_path": relative_path,
                    "doc_title": doc_title,
                    "section": chunk.section,
                },
            )
            if ok:
                ingested += 1
            else:
                print(f"  ! failed to upsert {doc_id}")
    return ingested


async def main() -> None:
    files = _find_markdown_files()
    if not files:
        print("No playbook markdown files found.")
        return

    total_chunks = 0
    for path in files:
        relative_path = path.relative_to(REPO_ROOT)
        count = await _ingest_file(path)
        total_chunks += count
        print(f"  {relative_path}: {count} chunk(s) ingested")

    print(f"\nDone — {len(files)} file(s) processed, {total_chunks} chunk(s) ingested into 'playbook'.")


if __name__ == "__main__":
    asyncio.run(main())
