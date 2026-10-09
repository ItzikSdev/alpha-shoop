"""Lia's market-research playbook: paraphrase-only pattern store + tool wiring."""
import pytest

from src.social_mcp import research


@pytest.fixture(autouse=True)
def _tmp_playbook(tmp_path, monkeypatch):
    monkeypatch.setattr(research, "_PATH", tmp_path / "pb.json")


def test_save_and_read_pattern():
    r = research.save_pattern("t", "BrandX", "question", "Tired of screens at dinner?", "pain, product, proof",
                              "Shop now", "pain first")
    assert r["ok"] and r["total_patterns"] == 1
    pb = research.read_playbook()
    assert pb["total"] == 1 and pb["hook_type_counts"] == {"question": 1}


def test_refuses_verbatim_long_copy_and_missing_fields():
    assert not research.save_pattern("t", "B", "question", "x" * 141, "s", "c", "w")["ok"]
    assert not research.save_pattern("t", "", "question", "h", "s", "c", "w")["ok"]


def test_duplicate_and_unknown_hook_type():
    a = research.save_pattern("t", "B", "weird", "same hook", "s", "c", "w")
    b = research.save_pattern("t", "B", "weird", "same hook", "s", "c", "w")
    assert b.get("duplicate") and a["id"] == b["id"]
    assert research.read_playbook()["patterns"][0]["hook_type"] == "other"


def test_tools_are_wired_for_lia():
    import ast
    from pathlib import Path

    from src.social_mcp import server
    src = Path(__file__).resolve().parents[1] / "src" / "org" / "social_agent.py"
    tree = ast.parse(src.read_text(encoding="utf-8"))
    agent_tools = {n.name for n in ast.walk(tree) if isinstance(n, ast.AsyncFunctionDef)}
    listed = next(n for n in tree.body if isinstance(n, ast.Assign) and n.targets[0].id == "TOOLS")
    in_list = {e.id for e in listed.value.elts}
    for name in ("ad_library_search", "web_social_search", "save_pattern", "social_playbook"):
        assert name in agent_tools and name in in_list and name in server.TOOL_NAMES
