"""
Visual knowledge graph — a local FalkorDB instance logging agent/tool/event
relations, e.g. `(Sol:Agent)-[:GENERATED]->(Banner:Media)`, browsable at
http://localhost:3001 (see docker-compose.yml's `falkordb` service).

The `falkordb` Python client is synchronous (redis-py under the hood), so
every call here runs inside `asyncio.to_thread(...)` — this module is safe
to call from async agent code without blocking the event loop.

Every public function is best-effort: a FalkorDB outage must never break an
agent run (the knowledge graph is observability, not a dependency). Errors
are caught and logged as a warning ONCE per process (not per-call) so a
stopped container doesn't spam the log for every tool execution.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

_GRAPH_NAME = "alpha_org"
_LABEL_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

_graph = None  # lazy singleton — the falkordb.Graph handle
_warned = False  # log the "FalkorDB unavailable" warning at most once per process


def _get_graph():
    """Lazy-connect to FalkorDB. Returns None (never raises) if the client
    library isn't installed or the server isn't reachable — callers treat
    None as "logging disabled this call."""
    global _graph
    if _graph is not None:
        return _graph
    try:
        from falkordb import FalkorDB
        host = os.environ.get("FALKORDB_HOST", "localhost")
        port = int(os.environ.get("FALKORDB_PORT", "6380"))
        db = FalkorDB(host=host, port=port)
        _graph = db.select_graph(_GRAPH_NAME)
        return _graph
    except Exception as exc:
        _warn_once(f"FalkorDB connection failed ({exc}) — knowledge-graph logging disabled")
        return None


def _warn_once(msg: str) -> None:
    global _warned
    if not _warned:
        logger.warning(msg)
        _warned = True


def _valid_label(label: str) -> bool:
    return bool(_LABEL_RE.match(label))


def _log_relation_sync(
    subject_label: str, subject_key: str,
    relation: str,
    object_label: str, object_key: str,
    props: dict | None,
) -> None:
    graph = _get_graph()
    if graph is None:
        return
    for label in (subject_label, relation, object_label):
        if not _valid_label(label):
            logger.warning("knowledge_graph: rejected unsafe label/relation %r", label)
            return
    now = datetime.now(timezone.utc).isoformat()
    # `name` is set alongside `key` because the FalkorDB Browser captions each
    # node with its `name` property and falls back to the bare internal id
    # otherwise — which is why the graph rendered as unlabelled numbered dots.
    query = (
        f"MERGE (s:{subject_label} {{key: $subject_key}}) "
        f"SET s.name = $subject_key "
        f"MERGE (o:{object_label} {{key: $object_key}}) "
        f"SET o.name = $object_key "
        f"MERGE (s)-[r:{relation}]->(o) "
        f"SET r += $props, r.updated_at = $now, r.created_at = coalesce(r.created_at, $now)"
    )
    graph.query(query, params={
        "subject_key": subject_key,
        "object_key": object_key,
        "props": props or {},
        "now": now,
    })


async def log_relation(
    subject_label: str, subject_key: str,
    relation: str,
    object_label: str, object_key: str,
    props: dict | None = None,
) -> None:
    """MERGE both nodes and the relation between them (idempotent — safe to
    call repeatedly for the same edge). Example:

        await log_relation("Agent", "Sol", "GENERATED", "Media", banner_id)

    produces (Sol:Agent)-[:GENERATED]->(Banner:Media) in the graph. Silently
    no-ops if FalkorDB isn't reachable."""
    try:
        await asyncio.to_thread(
            _log_relation_sync, subject_label, subject_key, relation, object_label, object_key, props,
        )
    except Exception as exc:  # noqa: BLE001
        _warn_once(f"FalkorDB write failed ({exc}) — knowledge-graph logging disabled")


def _log_tool_execution_sync(agent_name: str, tool_name: str, ok: bool, detail: str) -> None:
    graph = _get_graph()
    if graph is None:
        return
    if not _valid_label(agent_name) or not _valid_label(tool_name):
        logger.warning("knowledge_graph: rejected unsafe agent/tool key %r/%r", agent_name, tool_name)
        return
    now = datetime.now(timezone.utc).isoformat()
    # Every other edge in this module is a plain MERGE + overwrite (SET r += props)
    # — fine for "what's the current state", useless for "how often has this
    # happened". A recurring-failure gap can only be detected from a COUNT, so this
    # one edge accumulates attempts/fail_count instead of clobbering them each call.
    query = (
        "MERGE (a:Agent {key: $agent}) SET a.name = $agent "
        "MERGE (t:Tool {key: $tool}) SET t.name = $tool "
        "MERGE (a)-[r:EXECUTED]->(t) "
        "SET r.ok = $ok, r.detail = $detail, r.updated_at = $now, "
        "    r.created_at = coalesce(r.created_at, $now), "
        "    r.attempts = coalesce(r.attempts, 0) + 1, "
        "    r.fail_count = coalesce(r.fail_count, 0) + CASE WHEN $ok THEN 0 ELSE 1 END, "
        "    r.success_count = coalesce(r.success_count, 0) + CASE WHEN $ok THEN 1 ELSE 0 END"
    )
    graph.query(query, params={"agent": agent_name, "tool": tool_name, "ok": bool(ok),
                                "detail": detail[:200], "now": now})


async def log_tool_execution(agent_name: str, tool_name: str, ok: bool, detail: str = "") -> None:
    """Convenience wrapper for the common case: an agent ran a tool.
    Produces (agent_name:Agent)-[:EXECUTED {ok, attempts, fail_count, success_count}]->
    (tool_name:Tool), accumulating counts across calls (see _log_tool_execution_sync)."""
    try:
        await asyncio.to_thread(_log_tool_execution_sync, agent_name, tool_name, bool(ok), detail)
    except Exception as exc:  # noqa: BLE001
        _warn_once(f"FalkorDB write failed ({exc}) — knowledge-graph logging disabled")


async def log_delegation(from_agent: str, to_agent: str, task: str) -> None:
    """(from:Agent)-[:ASSIGNED {task}]->(to:Agent) — who asked whom to do what.

    This is the edge that makes the graph an org chart rather than a tool log:
    before agent→agent delegation existed there was nothing to draw here."""
    await log_relation(
        "Agent", from_agent, "ASSIGNED", "Agent", to_agent,
        props={"task": task[:200]},
    )


async def log_agent_turn(agent_name: str, action: str, detail: str = "") -> None:
    """(agent:Agent)-[:DECIDED]->(action:Action) — a proactive heartbeat turn.
    Gives every agent a presence in the graph, not just the ones that call
    tools, so an idle-but-thinking agent is still visible."""
    await log_relation(
        "Agent", agent_name, "DECIDED", "Action", action,
        props={"detail": detail[:200]},
    )


def _seed_org_graph_sync(members: list[tuple[str, str]], tools: dict[str, list[str]]) -> None:
    graph = _get_graph()
    if graph is None:
        return
    now = datetime.now(timezone.utc).isoformat()
    for name, role in members:
        graph.query(
            "MERGE (a:Agent {key: $key}) "
            "SET a.name = $key, a.role = $role, a.updated_at = $now, "
            "    a.created_at = coalesce(a.created_at, $now)",
            params={"key": name, "role": role, "now": now},
        )
    for owner, tool_names in tools.items():
        for tool_name in tool_names:
            graph.query(
                "MERGE (a:Agent {key: $agent}) SET a.name = $agent "
                "MERGE (t:Tool {key: $tool}) SET t.name = $tool "
                "MERGE (a)-[r:CAN_USE]->(t) "
                "SET r.created_at = coalesce(r.created_at, $now)",
                params={"agent": owner, "tool": tool_name, "now": now},
            )
    # Backfill any node created before `name` was written (older EXECUTED/
    # GENERATED nodes), so nothing renders as an unlabelled dot.
    graph.query("MATCH (n) WHERE n.name IS NULL AND n.key IS NOT NULL SET n.name = n.key")


async def seed_org_graph(members: list[tuple[str, str]], tools: dict[str, list[str]]) -> None:
    """Draw the org itself: every active agent as a node, and a CAN_USE edge to
    each tool they're capable of running.

    Without this the graph only ever contained agents that had already executed
    something — which in practice meant Sol alone, since his was the one loop
    wired to `log_tool_execution`. Seeding makes the whole company visible up
    front, and the EXECUTED/ASSIGNED edges then layer live activity on top."""
    try:
        await asyncio.to_thread(_seed_org_graph_sync, members, tools)
    except Exception as exc:  # noqa: BLE001
        _warn_once(f"FalkorDB seed failed ({exc}) — knowledge-graph logging disabled")


def _find_capability_gaps_sync(
    min_attempts: int, min_fail_count: int, stale_hours: float,
) -> list[dict]:
    graph = _get_graph()
    if graph is None:
        return []
    stale_before = (datetime.now(timezone.utc) - timedelta(hours=stale_hours)).isoformat()
    gaps: list[dict] = []

    # 1. An agent keeps EXECUTING a tool it has no CAN_USE edge for — either a
    #    tool name the LLM hallucinated, or one that legitimately belongs to a
    #    teammate. `attempts >= min_attempts` filters out a one-off typo.
    r = graph.query(
        "MATCH (a:Agent)-[e:EXECUTED]->(t:Tool) "
        "WHERE NOT (a)-[:CAN_USE]->(t) AND coalesce(e.attempts, 1) >= $min_attempts "
        "RETURN a.key, t.key, coalesce(e.attempts, 1), coalesce(e.fail_count, 0), e.detail",
        params={"min_attempts": min_attempts},
    )
    for agent, tool, attempts, fail_count, detail in (r.result_set or []):
        gaps.append({
            "gap_type": "no_can_use_edge",
            "agent": agent, "tool": tool,
            "evidence": (f"(({agent}:Agent)-[:EXECUTED]->({tool}:Tool) with no "
                         f"(({agent})-[:CAN_USE]->({tool}) edge — attempted {attempts}x, "
                         f"{fail_count} failed. Last result: {detail}"),
            "dedupe_key": f"gap:no_can_use:{agent}:{tool}",
        })

    # 2. A tool the agent DOES have keeps failing — the tool exists and is
    #    authorized, but something about it (creds, API shape, a bug) is broken.
    r = graph.query(
        "MATCH (a:Agent)-[e:EXECUTED]->(t:Tool) "
        "WHERE (a)-[:CAN_USE]->(t) AND coalesce(e.fail_count, 0) >= $min_fail_count "
        "RETURN a.key, t.key, coalesce(e.attempts, 1), e.fail_count, e.detail",
        params={"min_fail_count": min_fail_count},
    )
    for agent, tool, attempts, fail_count, detail in (r.result_set or []):
        gaps.append({
            "gap_type": "recurring_failure",
            "agent": agent, "tool": tool,
            "evidence": (f"(({agent}:Agent)-[:EXECUTED {{ok:false}}]->({tool}:Tool) — "
                         f"failed {fail_count} of {attempts} attempts. Last result: {detail}"),
            "dedupe_key": f"gap:recurring_failure:{agent}:{tool}",
        })

    # 3. A delegation that never produced a follow-up from the target agent.
    #    CAVEAT: ASSIGNED is MERGEd per (from,to) pair, not per task, so this can
    #    only see the MOST RECENT delegation between any two agents, not every
    #    individual ask ever made — an honest limitation of the current schema,
    #    not a bug. "Resolved" = the target DECIDED or EXECUTED anything after
    #    the ASSIGNED edge's own updated_at.
    r = graph.query(
        "MATCH (f:Agent)-[asg:ASSIGNED]->(to:Agent) "
        "WHERE asg.updated_at < $stale_before "
        "OPTIONAL MATCH (to)-[act:DECIDED]->(:Action) WHERE act.updated_at > asg.updated_at "
        "OPTIONAL MATCH (to)-[ex:EXECUTED]->(:Tool) WHERE ex.updated_at > asg.updated_at "
        "WITH f, to, asg, act, ex "
        "WHERE act IS NULL AND ex IS NULL "
        "RETURN f.key, to.key, asg.task, asg.updated_at",
        params={"stale_before": stale_before},
    )
    for from_agent, to_agent, task, assigned_at in (r.result_set or []):
        gaps.append({
            "gap_type": "unresolved_delegation",
            "agent": to_agent, "tool": None,
            "evidence": (f"(({from_agent}:Agent)-[:ASSIGNED {{task:{task!r}}}]->({to_agent}:Agent) "
                         f"at {assigned_at}, no DECIDED/EXECUTED edge from {to_agent} since — "
                         f"the ask appears to have gone nowhere."),
            "dedupe_key": f"gap:unresolved_delegation:{from_agent}:{to_agent}",
        })
    return gaps


async def find_capability_gaps(
    min_attempts: int = 2, min_fail_count: int = 3, stale_hours: float = 24.0,
) -> list[dict]:
    """READ-ONLY scan for the three gap signals Nova's weekly check looks for
    (no CAN_USE edge for a repeatedly-attempted tool, a CAN_USE'd tool that keeps
    failing, a delegation with no follow-up). Returns raw evidence for a human (or
    an LLM grounded in real docs) to judge — this function never writes anything
    and never decides on its own that a ticket should be filed."""
    try:
        return await asyncio.to_thread(
            _find_capability_gaps_sync, min_attempts, min_fail_count, stale_hours,
        )
    except Exception as exc:  # noqa: BLE001
        _warn_once(f"FalkorDB gap query failed ({exc})")
        return []


def _prune_sync(keys: list[str]) -> int:
    graph = _get_graph()
    if graph is None:
        return 0
    r = graph.query("MATCH (n) WHERE n.key IN $keys DETACH DELETE n RETURN count(n)",
                    params={"keys": keys})
    return int(r.result_set[0][0]) if r.result_set else 0


async def prune_nodes(keys: list[str]) -> int:
    """Delete nodes by key (and their edges). Used to clear test/debug leftovers."""
    try:
        return await asyncio.to_thread(_prune_sync, keys)
    except Exception as exc:  # noqa: BLE001
        _warn_once(f"FalkorDB prune failed ({exc})")
        return 0
