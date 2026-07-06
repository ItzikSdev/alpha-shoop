"""Tests: the REAL CJ MCP client (src/cj_mcp/client.py).

These are deterministic — CJ's live MCP endpoint is stubbed via a fake `_post`, so
no network, no token, and no exposure to CJ's per-IP rate limit.
"""
import pytest

from src.cj_mcp import client as cjc


class FakeResp:
    def __init__(self, text: str, headers: dict | None = None):
        self.text = text
        self.headers = headers or {}
        self.status_code = 200


def _sse(payload_json: str) -> str:
    """Wrap a JSON body the way CJ streams it back (Server-Sent Events)."""
    return f"event: message\ndata: {payload_json}\n\n"


def test_parse_sse_extracts_data_line():
    assert cjc._parse_sse(_sse('{"a":1}')) == {"a": 1}
    assert cjc._parse_sse("no data here") is None


def test_safe_json_falls_back_to_text():
    assert cjc._safe_json('{"x":2}') == {"x": 2}
    assert cjc._safe_json("not json") == "not json"


def _make_client(monkeypatch) -> cjc.CJMCPClient:
    # Bypass the token lookup + real handshake; we only exercise call().
    monkeypatch.setattr(cjc, "_endpoint", lambda: "https://example.test/mcp/TOKEN")
    c = cjc.CJMCPClient()
    c._client = object()  # sentinel; _post is replaced below
    return c


@pytest.mark.asyncio
async def test_call_parses_tool_json_result(monkeypatch):
    c = _make_client(monkeypatch)

    async def fake_post(payload):
        # CJ returns tool output as content[0].text, itself a JSON string.
        body = '{"jsonrpc":"2.0","id":9,"result":{"content":[{"type":"text","text":"{\\"stock\\":42}"}]}}'
        return FakeResp(_sse(body))

    monkeypatch.setattr(c, "_post", fake_post)
    out = await c.call("get_product_inventory", {"pid": "1", "countryCode": "US"})
    assert out == {"stock": 42}


@pytest.mark.asyncio
async def test_call_raises_throttled_on_rate_limit(monkeypatch):
    c = _make_client(monkeypatch)

    async def fake_post(payload):
        body = ('{"jsonrpc":"2.0","id":9,"result":{"content":[{"type":"text",'
                '"text":"Get product inventory failed: Too Many Requests, one ip limit 3 users"}]}}')
        return FakeResp(_sse(body))

    monkeypatch.setattr(c, "_post", fake_post)
    monkeypatch.setattr(cjc.asyncio, "sleep", _noop_sleep)  # don't actually wait during retries
    with pytest.raises(cjc.CJMCPThrottled):
        await c.call("get_product_inventory", {"pid": "1"}, retries=2)


@pytest.mark.asyncio
async def test_call_raises_on_jsonrpc_error(monkeypatch):
    c = _make_client(monkeypatch)

    async def fake_post(payload):
        return FakeResp(_sse('{"jsonrpc":"2.0","id":9,"error":{"code":-32000,"message":"bad"}}'))

    monkeypatch.setattr(c, "_post", fake_post)
    with pytest.raises(cjc.CJMCPError):
        await c.call("whatever", {})


async def _noop_sleep(*_a, **_k):
    return None
