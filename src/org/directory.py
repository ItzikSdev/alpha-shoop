"""
The company's capability directory — "who can do what", rendered for prompts.

THE PROBLEM THIS SOLVES: agents were told to "route video questions to Reel" but
were never told what Reel can actually DO. Each one saw only its own charter, so
nobody could delegate meaningfully and the knowledge graph showed agents with no
edges between them. The information already existed (the roster in SQLite, the
tool lists in tool_catalog.py) — it simply never reached anyone's prompt.

WHY NOT RAG: this is deliberately NOT a retrieval corpus. The directory is small
(one roster, a few dozen tools — a few hundred tokens), must be EXACT rather than
"top-k semantically similar" (asking "who renders video?" has one right answer,
not three plausible ones), and changes the moment the roster changes, which would
leave embeddings stale. RAG stays where it earns its keep: the CJ catalog, the
store's products, and the playbook docs — corpora too large to inline.

Everything here is derived at call time from the live roster + tool catalog, so
it can never drift out of sync with the company.
"""
from __future__ import annotations

from src.org.models import Agent, list_agents
from src.org.tool_catalog import AGENT_TOOL_GROUPS, all_tool_names


def capability_directory(exclude: str = "", skill_chars: int = 150) -> str:
    """A compact "who can do what" block for injection into any agent prompt.

    `exclude` drops one agent by name (an agent doesn't need itself in its own
    directory). Lists each teammate's role, what they're for, the tools they can
    actually run, and what they're working on right now."""
    lines: list[str] = []
    for a in list_agents(active_only=True):
        if exclude and a.name.lower() == exclude.lower():
            continue
        groups = AGENT_TOOL_GROUPS.get(a.name, {})
        caps = "; ".join(f"{group}: {', '.join(tools)}" for group, tools in groups.items())
        task = a.memory.get("assigned_task")
        lines.append(
            f"- {a.name} ({a.role}) — {a.skill[:skill_chars].strip()}"
            + (f"\n    CAN RUN → {caps}" if caps else "\n    (no tool loop — reports only)")
            + (f"\n    NOW → {str(task)[:100]}" if task else "")
        )
    if not lines:
        return "(you're the only agent on the roster)"
    return "\n".join(lines)


def who_can(capability: str) -> list[tuple[str, str]]:
    """[(agent_name, matching_tool)] for an exact/substring tool match.

    Deliberately exact rather than semantic: "who can place a supplier order"
    must resolve to Milo every time, not to whoever embeds closest."""
    needle = capability.strip().lower().replace(" ", "_")
    hits: list[tuple[str, str]] = []
    for agent, tools in all_tool_names().items():
        for tool in tools:
            if needle in tool.lower():
                hits.append((agent, tool))
    return hits


def routing_hint() -> str:
    """One line per agent: the shortest possible "send X to Y" table, for the
    message router and for prompts that only need addressing, not full detail."""
    return "\n".join(
        f"- {a.name} ({a.role}): {a.skill[:90].strip()}"
        for a in list_agents(active_only=True)
    )


def agent_by_name(name: str) -> Agent | None:
    target = name.strip().lower()
    return next(
        (a for a in list_agents(active_only=True)
         if a.name.lower() == target or a.role.lower() == target),
        None,
    )
