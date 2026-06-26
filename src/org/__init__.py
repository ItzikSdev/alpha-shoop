"""
src/org — the "living company" layer.

A self-managing organization of agent personas that sits ABOVE the existing
single-store pipeline (`src/agents/orchestrator.py`). It hires employees, holds
meetings, makes decisions, runs real store-building pipelines to earn real
money, and grows headcount when real revenue justifies it.

Public surface:
  - models     : persistence (Agent / Meeting / Company) in traces.db
  - seed       : founding team + company bootstrap
  - meeting    : multi-persona meeting → structured decisions
  - lifecycle  : onboarding, continuous-learning retrospective, team-building
  - executor   : turn decisions into real actions (hiring, _spawn_run)
  - daemon     : the autonomous org_tick() loop
"""
from src.org.models import (
    Agent,
    Company,
    Meeting,
    add_meeting,
    get_agent,
    get_company,
    init_org_tables,
    list_agents,
    list_meetings,
    new_agent,
    new_meeting,
    save_agent,
    save_company,
)

__all__ = [
    "Agent", "Company", "Meeting",
    "init_org_tables",
    "list_agents", "get_agent", "save_agent", "new_agent",
    "add_meeting", "list_meetings", "new_meeting",
    "get_company", "save_company",
]
