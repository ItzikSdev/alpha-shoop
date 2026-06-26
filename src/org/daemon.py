"""
The autonomous heartbeat of the company.

`run_org_cycle()` runs ONE full company cycle (retrospective → meeting →
execute), wrapped in a trace run so it streams live to the same Runs UI/SSE the
pipeline uses — and so every meeting LLM call is token-traced (you can verify
the cheap calls went to the local Ollama model, not Anthropic).

`org_tick()` is the time-gated wrapper the background loop calls every ~30s: it
only fires a cycle when the daemon is enabled, the interval has elapsed, no
pipeline run is already in flight (anti-pileup), and the kill-switch is off.

Both are also callable directly: POST /org/tick runs `run_org_cycle()` once
(manual now), while flipping the daemon on lets `org_tick()` drive it 24/7.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from src.org.lifecycle import run_retrospective
from src.org.executor import execute_decisions
from src.org.meeting import hold_meeting
from src.org.models import Company, get_company, save_company
from src.org.seed import seed_founding_team
from src.org.slack import post_meeting
from src.tracing import trace_store, TraceCallback, current_thread_id, current_trace_callback
from src.tracing.persist import save_all

logger = logging.getLogger(__name__)

# Per-cycle LLM-call ceiling — a guardrail against a runaway cycle. The retro is
# deterministic and a meeting is one call, so a healthy cycle is ~1 call; the
# cap leaves headroom for onboarding/train calls on a big hiring round.
_MAX_LLM_CALLS_PER_CYCLE = 12


def _pick_kind(tick_count: int) -> str:
    """Cadence: mostly standups, periodic strategy, occasional team-building."""
    if tick_count > 0 and tick_count % 5 == 4:
        return "teambuilding"
    if tick_count % 3 == 0:
        return "strategy"
    return "standup"


async def run_org_cycle(kind: str | None = None) -> dict:
    """Run one full company cycle. Returns a summary dict."""
    company = seed_founding_team()
    tick_count = int(company.daemon.get("tick_count", 0))
    chosen = kind or _pick_kind(tick_count)

    thread_id = str(uuid.uuid4())
    trace_store.start_run(thread_id=thread_id, task=f"[ORG] {chosen} cycle", operator="org")
    current_thread_id.set(thread_id)
    current_trace_callback.set(TraceCallback())

    actions: list[str] = []
    try:
        await run_retrospective()                 # continuous learning (deterministic)
        meeting = await hold_meeting(chosen)       # the discussion → decisions

        run = trace_store.get_run(thread_id)
        if run and len(run.llm_calls) > _MAX_LLM_CALLS_PER_CYCLE:
            logger.warning("Org cycle hit LLM-call ceiling — skipping execution")
        else:
            actions = await execute_decisions(meeting)  # real actions (incl. _spawn_run)

        # Narrate the meeting into the shared Slack channel (best-effort no-op
        # if SLACK_WEBHOOK_URL is unset) — you + the agents in one feed.
        await post_meeting(meeting.kind, meeting.notes, meeting.decisions, actions)

        # Advance daemon bookkeeping.
        company = get_company() or company
        company.daemon["tick_count"] = tick_count + 1
        company.daemon["last_tick_at"] = datetime.now(timezone.utc).isoformat()
        save_company(company)

        trace_store.finish_run(thread_id, "completed")
        return {
            "thread_id": thread_id,
            "kind": chosen,
            "meeting_id": meeting.meeting_id,
            "decisions": meeting.decisions,
            "actions": actions,
        }
    except Exception as exc:
        logger.exception("Org cycle %s failed", thread_id)
        trace_store.finish_run(thread_id, "failed")
        return {"thread_id": thread_id, "kind": chosen, "error": str(exc), "actions": actions}
    finally:
        import asyncio
        await asyncio.to_thread(save_all, trace_store)


def _interval_elapsed(company: Company) -> bool:
    last = company.daemon.get("last_tick_at")
    if not last:
        return True
    interval = int(company.daemon.get("interval_minutes", 60))
    since_min = (datetime.now(timezone.utc) - datetime.fromisoformat(last)).total_seconds() / 60
    return since_min >= interval


async def org_tick() -> None:
    """Time-gated cycle, called by the background loop. No-op unless it's time."""
    company = get_company()
    if not company or not company.daemon.get("enabled"):
        return
    if not _interval_elapsed(company):
        return

    # Anti-pileup: don't start a cycle while any pipeline run is still going
    # (same guard main.py's daemon uses). Builds spawned by the last cycle must
    # finish before we make new decisions.
    if any(r.status in ("running", "pending") for r in trace_store.list_runs()[:3]):
        return

    # Respect the global kill-switch (lazy import avoids a route import cycle).
    try:
        from src.api.routes.agents import _kill_switch
        if _kill_switch.is_active:
            return
    except Exception:
        pass

    logger.info("Org daemon: firing company cycle")
    await run_org_cycle()
