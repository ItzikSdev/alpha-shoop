"""
Read-only access to the two root-level org-context docs — docs/DECISIONS_LOG.md
(chronological record of what's already been diagnosed/tried) and
docs/VISION_ROADMAP.md (current phase + the explicitly out-of-scope/deferred
list). Grounding for Nova: before proposing an idea or filing a gap ticket she
reads these so she doesn't re-suggest something already tried today or
something explicitly deferred.

Deliberately READ ONLY — unlike design_files.py (which pairs a read with a
write for the store templates Grace/Linus are meant to edit), there is no
write_org_docs here. These two files are a human-maintained record; no agent
gets to rewrite them as part of this capability.
"""
from __future__ import annotations

from pathlib import Path

_DOCS_ROOT = (Path(__file__).resolve().parents[2] / "docs").resolve()
_DECISIONS_LOG = _DOCS_ROOT / "DECISIONS_LOG.md"
_VISION_ROADMAP = _DOCS_ROOT / "VISION_ROADMAP.md"


def read_org_docs() -> dict:
    """Return the full text of both docs. Empty string for either that doesn't
    exist yet (never raises — grounding context is best-effort, not a dependency
    an agent's turn should fail over)."""
    def _read(p: Path) -> str:
        try:
            return p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return ""
    return {
        "decisions_log": _read(_DECISIONS_LOG),
        "vision_roadmap": _read(_VISION_ROADMAP),
    }
