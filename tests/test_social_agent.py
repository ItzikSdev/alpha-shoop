"""Lia's tool loop end-to-end over the REAL social MCP server (stdio), with a scripted
fake model — proves the wiring: tool calls reach the MCP server, drafts land in the
queue as pending, and nothing publishes without approval."""
from __future__ import annotations

import sys
import types

import pytest
from langchain_core.messages import AIMessage


class _ScriptedLLM:
    def __init__(self, script):
        self.script = list(script)

    def bind_tools(self, tools):
        return self

    async def ainvoke(self, messages):
        return self.script.pop(0)


@pytest.fixture
def lia(monkeypatch, tmp_path):
    monkeypatch.setenv("SOCIAL_QUEUE_PATH", str(tmp_path / "q.json"))  # the MCP subprocess reads this
    from src.social_mcp import queue
    monkeypatch.setattr(queue, "_PATH", tmp_path / "q.json")          # this process reads the same file
    monkeypatch.setenv("TRACES_DB_PATH", str(tmp_path / "traces.db"))
    for k in ("META_PAGE_ID", "META_ACCESS_TOKEN", "FB_PAGE_ACCESS_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    script = [
        AIMessage(content="", tool_calls=[{"id": "1", "name": "social_status", "args": {}}]),
        AIMessage(content="", tool_calls=[{"id": "2", "name": "draft_post", "args": {
            "platform": "instagram", "kind": "photo", "message": "Bath time, upgraded.",
            "media_url": "https://cdn.shopify.com/x.jpg", "rationale": "test"}}]),
        AIMessage(content="", tool_calls=[{"id": "3", "name": "list_drafts", "args": {"status": "pending"}}]),
        AIMessage(content="Drafted 1 Instagram post; Facebook/Instagram not connected: META_PAGE_ID missing."),
    ]
    fake_llm_mod = types.ModuleType("src.llm")
    fake_llm_mod.get_llm = lambda *a, **k: _ScriptedLLM(script)
    monkeypatch.setitem(sys.modules, "src.llm", fake_llm_mod)
    fake_tg = types.ModuleType("src.org.telegram")

    async def post_as(*a, **k):
        return True
    fake_tg.post_as = post_as
    monkeypatch.setitem(sys.modules, "src.org.telegram", fake_tg)
    sys.modules.pop("src.org.social_agent", None)
    sys.modules.pop("src.org.agent_runs", None)
    import src.org.social_agent as mod
    return mod


@pytest.mark.asyncio
async def test_lia_drafts_through_real_mcp_and_nothing_publishes(lia):
    from src.social_mcp import queue
    r = await lia.run_social_task("Make one Instagram post for the bathtub", narrate=False)
    assert "Drafted 1 Instagram post" in r["final"]
    drafts = queue.list_drafts()
    assert len(drafts) == 1 and drafts[0]["status"] == "pending" and drafts[0]["author"] == "Lia"
