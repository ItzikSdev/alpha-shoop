"""
Evaluator worker — the self-correction node of the autonomous flow (docs/prompt.md §2).

Sits between the Product Hunter (trend_scraper) and the Shopify Developer
(ecommerce_manager). The Hunter sources candidates and enriches them with CJ
shipping cost; the Evaluator scores each candidate's REAL net margin — after the
strict 18% VAT and payment-processing fees (src/agents/pricing.py) — and decides:

  - APPROVE  → the best batch clears the net-margin threshold. It annotates every
               candidate with its net margin and hands the batch on; the
               ecommerce_manager lists the winners.
  - REJECT   → the whole batch is below target. It records WHY into
               `sourcing_feedback` so the Hunter re-searches a different/higher-
               margin cluster, and bumps `loop_counter`.

The hard `max_loops` cap lives in the orchestrator (which owns the loop and the
Slack "gave up" notice) — this node only scores and votes. It is pure-Python +
the existing pricing model: no LLM call, so it adds zero token cost to the loop.

Threshold note: gross sourcing already floors at 30% (sourcing.py min_margin),
which nets out to roughly 10–15% after VAT+fees, so MIN_NET_MARGIN defaults to a
realistic 0.10 — set it higher via env to be stricter. Too high a bar just starves
the catalog and burns CJ calls looping.
"""
from __future__ import annotations

import os

from src.agents.pricing import annotate_candidate
from src.agents.state import AgentState
from src.tracing import agent_log
from src.tracing.context import current_node

MIN_NET_MARGIN = float(os.environ.get("MIN_NET_MARGIN", "0.10"))


async def evaluator_node(state: AgentState) -> dict:
    """Score the current `trending_products` batch on net margin; approve or reject."""
    current_node.set("evaluator")
    candidates = state.get("trending_products") or []

    if not candidates:
        # Nothing to score — let the orchestrator's normal empty-batch handling run.
        return {"pricing_calc": {"approved": False, "reason": "no candidates", "best_net_margin": 0.0}}

    annotated = [annotate_candidate(c) for c in candidates]
    annotated.sort(key=lambda c: c.get("net_margin_pct", 0.0), reverse=True)
    best = annotated[0]
    best_margin = best.get("net_margin_pct", 0.0)
    keepers = [c for c in annotated if c.get("net_margin_pct", 0.0) >= MIN_NET_MARGIN]

    pricing_calc = {
        "approved": bool(keepers),
        "threshold": MIN_NET_MARGIN,
        "best_net_margin": best_margin,
        "best_title": best.get("title", ""),
        "best_breakdown": best.get("net_margin_breakdown", {}),
        "kept": len(keepers),
        "scored": len(annotated),
    }

    if keepers:
        agent_log(
            f"✅ Evaluator: {len(keepers)}/{len(annotated)} candidates clear "
            f"{MIN_NET_MARGIN:.0%} net margin (best {best_margin:.1%} — "
            f"'{best.get('title', '')[:40]}'). Approving.",
            "success",
        )
        # Pass the net-margin-annotated batch downstream so ecommerce_manager can
        # rank/list by REAL net margin, and so the Devon "going live" Slack gate
        # has the numbers. Keepers first (best margin at the top).
        return {
            "trending_products": keepers + [c for c in annotated if c not in keepers],
            "pricing_calc": pricing_calc,
            "workflow_status": "running",
        }

    # Whole batch below target → self-correct: tell the Hunter to look elsewhere.
    loop_counter = int(state.get("loop_counter", 0)) + 1
    feedback = (
        f"All {len(annotated)} candidates are below the {MIN_NET_MARGIN:.0%} net-margin "
        f"target (best was {best_margin:.1%} after 18% VAT + fees). Search a different, "
        f"higher-margin product cluster (lower supplier cost or higher resale value)."
    )
    agent_log(
        f"🔁 Evaluator REJECTED batch (best net margin {best_margin:.1%} < "
        f"{MIN_NET_MARGIN:.0%}) — self-correction loop {loop_counter}.",
        "warning",
    )
    return {
        "trending_products": [],
        "loop_counter": loop_counter,
        "sourcing_feedback": feedback,
        "pricing_calc": pricing_calc,
        "workflow_status": "running",
    }
