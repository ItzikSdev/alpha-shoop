"""Tests for the living-company org layer (src/org/*)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.org import models
from src.org import meeting as meeting_mod
from src.org import lifecycle as lifecycle_mod


@pytest.fixture
def org_db(tmp_path, monkeypatch):
    """Point the org tables at an isolated temp SQLite DB and init the schema."""
    db = tmp_path / "org_test.db"
    monkeypatch.setattr(models, "_DB_PATH", Path(db))
    models.init_org_tables()
    return db


# ── Seed ──────────────────────────────────────────────────────────────────────

def test_seed_founding_team_idempotent(org_db):
    from src.org.seed import seed_founding_team

    c1 = seed_founding_team()
    assert c1.headcount == 3
    roster = models.list_agents()
    assert {a.role for a in roster} == {"CEO", "CTO", "HR"}
    # Every founder has an explicit, non-empty skill (the user's core requirement).
    assert all(a.skill.strip() for a in roster)

    # Re-seeding must not duplicate anyone.
    seed_founding_team()
    assert models.get_company().headcount == 3
    assert len(models.list_agents()) == 3


# ── Hiring is gated on real revenue ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_hire_denied_without_revenue(org_db, monkeypatch):
    from src.org import executor
    from src.org.seed import seed_founding_team

    seed_founding_team()  # treasury starts at 0
    monkeypatch.setattr(executor, "onboard_agent", AsyncMock())
    monkeypatch.setattr(executor, "post_hire", AsyncMock())

    meeting = models.new_meeting("strategy")
    meeting.decisions = [{"type": "hire", "role": "marketer", "skill": "runs ads"}]
    actions = await executor.execute_decisions(meeting)

    assert any("DENIED" in a for a in actions)
    assert len(models.list_agents()) == 3  # nobody hired


@pytest.mark.asyncio
async def test_hire_succeeds_with_treasury(org_db, monkeypatch):
    from src.org import executor
    from src.org.seed import seed_founding_team

    company = seed_founding_team()
    company.treasury_usd = 1000.0  # plenty to afford a 4th head
    models.save_company(company)

    monkeypatch.setattr(executor, "onboard_agent", AsyncMock())
    monkeypatch.setattr(executor, "post_hire", AsyncMock())

    meeting = models.new_meeting("strategy")
    meeting.decisions = [{
        "type": "hire", "role": "marketer",
        "skill": "Launches and optimizes paid ad campaigns.", "team": "growth",
    }]
    actions = await executor.execute_decisions(meeting)

    assert any("hire(marketer)" in a for a in actions)
    roles = [a.role for a in models.list_agents()]
    assert "marketer" in roles
    assert models.get_company().headcount == 4
    executor.onboard_agent.assert_awaited()  # new hire was onboarded


# ── build_store routes through the REAL pipeline entry point ──────────────────

@pytest.mark.asyncio
async def test_build_store_decision_spawns_run(org_db, monkeypatch):
    from src.org import executor
    from src.org.seed import seed_founding_team
    import src.api.routes.agents as agents_route

    seed_founding_team()
    spawn = MagicMock()
    monkeypatch.setattr(agents_route, "_spawn_run", spawn)

    meeting = models.new_meeting("standup")
    meeting.decisions = [{"type": "build_store", "niche": "yoga mats", "budget_usd": 80}]
    await executor.execute_decisions(meeting)

    spawn.assert_called_once()
    # task carries the niche; operator attributes it to the org
    _args, kwargs = spawn.call_args
    called = " ".join(str(a) for a in _args) + str(kwargs)
    assert "yoga mats" in called


# ── Meeting JSON parsing is robust to fenced / prose-wrapped output ───────────

@pytest.mark.asyncio
async def test_hold_meeting_parses_fenced_json(org_db, monkeypatch):
    from src.org.seed import seed_founding_team

    seed_founding_team()
    monkeypatch.setattr(meeting_mod, "list_stores", lambda: [])  # no stores → no network

    fake_resp = MagicMock()
    fake_resp.content = (
        "Sure! Here is the plan:\n```json\n"
        '{"summary":"Build first store","decisions":'
        '[{"type":"build_store","niche":"candles","budget_usd":100}]}'
        "\n```\nLet me know!"
    )
    fake_llm = MagicMock()
    fake_llm.ainvoke = AsyncMock(return_value=fake_resp)
    monkeypatch.setattr(meeting_mod, "get_llm", lambda *a, **k: fake_llm)

    m = await meeting_mod.hold_meeting("standup")
    assert m.notes == "Build first store"
    assert m.decisions[0]["type"] == "build_store"
    assert m.decisions[0]["niche"] == "candles"


@pytest.mark.asyncio
async def test_hold_meeting_degrades_on_bad_json(org_db, monkeypatch):
    from src.org.seed import seed_founding_team

    seed_founding_team()
    monkeypatch.setattr(meeting_mod, "list_stores", lambda: [])

    fake_resp = MagicMock()
    fake_resp.content = "I couldn't decide anything useful, sorry."
    fake_llm = MagicMock()
    fake_llm.ainvoke = AsyncMock(return_value=fake_resp)
    monkeypatch.setattr(meeting_mod, "get_llm", lambda *a, **k: fake_llm)

    m = await meeting_mod.hold_meeting("standup")
    assert m.decisions == []  # safe degrade, no crash


# ── Continuous learning: retrospective ties decisions to real revenue ─────────

@pytest.mark.asyncio
async def test_retrospective_writes_lesson_and_accrues_treasury(org_db, monkeypatch):
    from src.org.seed import seed_founding_team

    company = seed_founding_team()

    # A prior meeting whose snapshot recorded $0 revenue.
    prior = models.new_meeting("strategy")
    prior.context_snapshot = {"revenue_7d_total_usd": 0.0}
    prior.decisions = [{"type": "build_store", "niche": "candles"}]
    prior.attendees = [a.agent_id for a in models.list_agents()]
    models.add_meeting(prior)

    # Now revenue is $120 → retrospective should accrue treasury and learn.
    monkeypatch.setattr(
        lifecycle_mod, "gather_snapshot",
        AsyncMock(return_value={"revenue_7d_total_usd": 120.0}),
    )

    lesson = await lifecycle_mod.run_retrospective()
    assert lesson and "120" in lesson
    updated = models.get_company()
    assert updated.treasury_usd == 120.0
    assert updated.lessons  # lesson recorded company-wide


# ── Team-building folds into shared culture ───────────────────────────────────

def test_teambuilding_folds_into_culture(org_db):
    from src.org.seed import seed_founding_team

    seed_founding_team()
    m = models.new_meeting("teambuilding")
    m.decisions = [{"type": "record_lesson", "lesson": "Celebrate small wins."}]
    lifecycle_mod.fold_teambuilding_into_culture(m)

    values = models.get_company().culture.get("values", [])
    assert "Celebrate small wins." in values
