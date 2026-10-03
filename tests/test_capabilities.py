"""Capability check reports missing connections by env NAME, never value."""
from __future__ import annotations

from src.org import capabilities as cap


def test_not_connected_when_env_missing(monkeypatch):
    monkeypatch.delenv("SERPER_API_KEY", raising=False)
    c = cap.agent_capabilities("Nova")
    nc = {x["tool"]: x["missing_env"] for x in c["not_connected"]}
    assert nc["search_web"] == ["SERPER_API_KEY"]
    assert c["ok"] is False


def test_connected_when_env_present(monkeypatch):
    monkeypatch.setenv("SERPER_API_KEY", "secret-value-xyz")
    c = cap.agent_capabilities("Nova")
    assert "search_web" in c["connected"]
    assert "secret-value-xyz" not in str(c)


def test_role_needs_reported_and_prompt_mentions_them(monkeypatch):
    c = cap.agent_capabilities("Kai")
    assert any("Meta" in m["need"] for m in c["missing_tools"])
    line = cap.capability_prompt_line("Kai")
    assert "flag_blocker" in line and "Meta" in line


def test_all_capabilities_covers_every_cataloged_agent():
    names = {c["agent"] for c in cap.all_capabilities()}
    assert set(cap.AGENT_TOOL_GROUPS) <= names
