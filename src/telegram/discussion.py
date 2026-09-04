"""
Inter-agent Telegram discussions — a bounded, multi-turn debate where the
team (Sol, Reel, Nora, Milo, Ava, or a chosen subset) talks through a topic
together in the shared Telegram group, each turn in that agent's own voice,
using the local Qwen3 model (src.graph.llm.get_graph_llm — never touches the
Anthropic budget). Triggered as a "discuss" decision from hold_meeting()
(see src/org/meeting.py's _DECISION_SPEC) and run by
src.org.executor.execute_decisions.

Safety boundary, by construction: this module never imports
save_company/save_agent/update_company/update_agent — a discussion cannot
mutate Company/Agent state directly, full stop. Its only three effects are:
  1. Telegram posts (the conversation itself).
  2. Knowledge-graph fact logging (src.graph.knowledge_graph — observability,
     not core state; best-effort/non-fatal like everywhere else it's used).
  3. If the team converges on a concrete next step, filing a PENDING proposal
     via src.org.proposals.create_proposal — it sits unexecuted until approved
     through the existing proposal flow, exactly like Grace's Shopify writes.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage

from src.org.conversation import company_language
from src.org.models import list_agents
from src.org.proposals import create_proposal
from src.org.telegram import post_as, post_to_telegram
from src.graph.llm import get_graph_llm
from src.graph.knowledge_graph import log_relation

logger = logging.getLogger(__name__)

_MAX_TURNS_DEFAULT = 4  # within the requested 3-5 cap


def _parse_json(text: str) -> dict:
    text = text.strip()
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        text = m.group(0)
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```\s*$", "", text)
    return json.loads(text.strip())


def _safe_relation(raw: str) -> str:
    """knowledge_graph.log_relation only accepts ^[A-Za-z_][A-Za-z0-9_]*$ for
    labels/relations (Cypher can't parametrize those) — sanitize an
    LLM-extracted relation string into that shape instead of silently
    dropping the fact."""
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", raw or "").strip("_").upper()[:40]
    return cleaned or "RELATED_TO"


_DEBATE_SYSTEM_TMPL = (
    "You are {name}, {role} at Alpha, an autonomous e-commerce company. Your "
    "teammates are discussing this topic together in the group chat:\n"
    "TOPIC: {topic}\n\n"
    "Your job (skill): {skill}\n"
    "Speak in FIRST PERSON, 1-3 sentences, in character. Build on what's "
    "already been said — add a NEW point, question, or piece of expertise "
    "from your role; never just repeat a teammate. If you disagree, say so "
    "plainly and why.\n"
    "Write in {lang}.\n\n"
    "CONVERSATION SO FAR (oldest first):\n{transcript}"
)

_FACTS_SYSTEM = (
    "You just watched a team discussion transcript. Extract up to 6 concrete, "
    "reusable facts or decisions worth remembering as (subject, relation, "
    "object) triples for the company's knowledge graph. Use SHORT relation "
    "verbs in ALL_CAPS (e.g. SUGGESTED, RAISED, AGREED_ON, FLAGGED). "
    "subject/object should be short names or concepts (e.g. an agent name, a "
    "product, an issue) — never invent one that wasn't actually said. If the "
    "team converged on a concrete NEXT ACTION someone should take, also give "
    "a one-sentence 'proposed_action' describing it (empty string if none — "
    "most discussions won't have one, don't force it).\n"
    'Output ONLY JSON: {"facts":[{"subject":"...","relation":"...","object":"..."}, ...],'
    ' "proposed_action":"..."}'
)


async def _extract_facts(topic: str, transcript: list[dict]) -> dict:
    """Best-effort — a failed/empty extraction just means nothing gets logged,
    never breaks the discussion."""
    text = "\n".join(f"{t['name']}: {t['text']}" for t in transcript)
    try:
        llm = get_graph_llm(temperature=0.1, max_tokens=500)
        resp = await llm.ainvoke([
            SystemMessage(content=_FACTS_SYSTEM),
            HumanMessage(content=f"Topic: {topic}\n\nTranscript:\n{text}"),
        ])
        return _parse_json(str(resp.content))
    except Exception as exc:
        logger.warning("Discussion fact-extraction failed (%s) — skipping", exc)
        return {"facts": [], "proposed_action": ""}


async def run_agent_discussion(
    topic: str,
    participants: list[str] | None = None,
    max_turns: int = _MAX_TURNS_DEFAULT,
) -> dict:
    """Run one bounded multi-turn discussion, posted live to the shared
    Telegram group (thread_override=None — General, not each agent's own
    topic, so it reads as one conversation — same pattern as
    src.org.manager.run_daily_meeting). Returns a summary dict."""
    max_turns = max(2, min(max_turns, 5))  # hard cap, per spec (3-5 max)
    agents = list_agents(active_only=True)
    if participants:
        wanted = {p.lower() for p in participants}
        matched = [a for a in agents if a.name.lower() in wanted]
        agents = matched or agents
    if len(agents) < 2:
        return {"topic": topic, "turns": [], "facts_logged": 0, "proposal_id": None,
                "note": "fewer than 2 active agents — nothing to discuss"}

    lang = company_language()
    await post_to_telegram(f"🗣️ *Team discussion:* {topic}")

    transcript: list[dict] = []
    for i in range(max_turns):
        speaker = agents[i % len(agents)]
        history = ("\n".join(f"{t['name']}: {t['text']}" for t in transcript)
                   or "(nobody has spoken yet — you're first)")
        system = _DEBATE_SYSTEM_TMPL.format(
            name=speaker.name, role=speaker.role, topic=topic,
            skill=speaker.skill, lang=lang, transcript=history,
        )
        try:
            llm = get_graph_llm(temperature=0.6, max_tokens=300)
            resp = await llm.ainvoke([
                SystemMessage(content=system),
                HumanMessage(content="Say your piece now."),
            ])
            text = str(resp.content).strip()
        except Exception as exc:
            logger.warning("Discussion turn failed for %s (%s) — skipping turn", speaker.name, exc)
            continue
        if not text:
            continue
        transcript.append({"name": speaker.name, "text": text})
        await post_as(speaker.name, speaker.role, text, thread_override=None)
        if i < max_turns - 1:
            await asyncio.sleep(1.0)

    facts_logged = 0
    proposal_id = None
    if transcript:
        extracted = await _extract_facts(topic, transcript)
        for fact in (extracted.get("facts") or [])[:6]:
            subject, relation, obj = fact.get("subject"), fact.get("relation"), fact.get("object")
            if not (subject and relation and obj):
                continue
            try:
                await log_relation(
                    "Concept", str(subject)[:120], _safe_relation(str(relation)),
                    "Concept", str(obj)[:120], props={"topic": topic[:200]},
                )
                facts_logged += 1
            except Exception:
                pass  # log_relation is already best-effort/non-fatal internally

        proposed_action = (extracted.get("proposed_action") or "").strip()
        if proposed_action:
            proposal_id = create_proposal(
                agent="team_discussion", kind="discussion_action",
                payload={"topic": topic, "action": proposed_action,
                         "participants": [t["name"] for t in transcript]},
                reason=f"Emerged from a team discussion on: {topic}",
            )
            await post_to_telegram(
                f"📋 Discussion concluded — a next step was proposed and is "
                f"PENDING approval [{proposal_id}]: {proposed_action}"
            )

    return {"topic": topic, "turns": transcript, "facts_logged": facts_logged,
            "proposal_id": proposal_id}
