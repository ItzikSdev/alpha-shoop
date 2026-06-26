"""
Self-awareness: let the company SEE its own operational health so the agents can
diagnose and heal themselves instead of a human patching them.

`run_health_summary()` turns the raw run traces into the picture an agent needs:
how many runs completed vs failed vs are stuck, which recent runs failed (and
why), and which are hung. Fed into each agent's turn, this is what lets an agent
reason "my last 8 boosts are all stuck and earned nothing — stop, clean up, and
flag the real blocker" entirely on its own.

`cancel_stuck_runs()` is the lever that turns that realization into action: it
marks runs that have been running far too long as failed, so the team can stop
piling more work behind a hung pipeline.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from src.tracing import trace_store

# Design/build pipeline runs are legitimately slow (large CSS generation,
# product sourcing) — keep this well above their normal duration so the
# self-healing cleanup doesn't kill healthy in-progress work.
_STUCK_MINUTES = 12.0


def _age_minutes(started_at: str) -> float:
    try:
        return (datetime.now(timezone.utc) - datetime.fromisoformat(started_at)).total_seconds() / 60
    except Exception:
        return 0.0


def _last_error(run) -> str:
    """Best-effort: the last warning/error log line of a run, for diagnosis."""
    for entry in reversed(getattr(run, "logs", [])):
        if entry.level in ("error", "warning"):
            return f"{entry.node}: {entry.msg}"[:120]
    # fall back to the very last thing it logged before dying
    logs = getattr(run, "logs", [])
    return (f"{logs[-1].node}: {logs[-1].msg}"[:120]) if logs else "(no logs)"


def run_health_summary(limit: int = 40, window_minutes: float = 60.0) -> str:
    """A compact, agent-readable health report of RECENT runs.

    Only counts runs from the last `window_minutes` so a one-time burst of old
    failures (e.g. a cancelled pile-up) doesn't poison the picture forever and
    trap the agents in a doom loop — they should judge current reality."""
    runs = [r for r in trace_store.list_runs()[:limit] if _age_minutes(r.started_at) <= window_minutes]
    if not runs:
        return "No runs in the last hour — a clean slate. Proceed."

    counts = Counter(r.status for r in runs)
    stuck = [r for r in runs if r.status in ("running", "pending") and _age_minutes(r.started_at) > _STUCK_MINUTES]
    failed = [r for r in runs if r.status == "failed"]

    lines = [
        f"Runs (last {len(runs)}): "
        f"{counts.get('completed', 0)} completed · {counts.get('failed', 0)} failed · "
        f"{counts.get('running', 0) + counts.get('pending', 0)} running ({len(stuck)} of them STUCK >3min)."
    ]
    if stuck:
        lines.append(f"⚠️ {len(stuck)} runs are hung — likely a broken/slow step. Consider cancel_stuck_runs and a different approach.")
    if failed:
        lines.append("Recent failures (diagnose the pattern):")
        for r in failed[:3]:
            lines.append(f"  - {r.operator}: {r.task[:45]} → {_last_error(r)}")
    return "\n".join(lines)


def pipeline_run_active() -> bool:
    """True if a real store pipeline run (not an org/meeting/heartbeat run) is
    in flight. Used to serialise heavy pipeline work to one at a time — the CJ
    sourcing step is globally rate-limited (1 QPS), so many concurrent runs jam
    behind it and look 'stuck'. Org runs (task starts with '[ORG]') don't count."""
    for r in trace_store.list_runs()[:10]:
        if r.status in ("running", "pending") and not (r.task or "").startswith("[ORG]"):
            return True
    return False


def cancel_stuck_runs() -> int:
    """Mark long-hung runs as failed so the team stops piling work behind them.
    Returns how many were cleaned up. This is a real self-healing lever the
    agents can pull on their own."""
    n = 0
    for r in trace_store.list_runs():
        if r.status in ("running", "pending") and _age_minutes(r.started_at) > _STUCK_MINUTES:
            trace_store.finish_run(r.thread_id, "failed")
            n += 1
    return n
