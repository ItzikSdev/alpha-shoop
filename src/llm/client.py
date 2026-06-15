"""
LiteLLM proxy client factory.

Every agent gets its LLM from here — one line, no model IDs in agent code.
The proxy at LITELLM_PROXY_URL maps aliases → real Anthropic models and
handles retries, cost tracking, and future model swaps transparently.

Usage:
    from src.llm import get_llm

    llm = get_llm("director")                    # ChatOpenAI → proxy → claude-opus-4-8
    llm = get_llm("scraper",  temperature=0.0)   # ChatOpenAI → proxy → claude-haiku-4-5
    llm = get_llm("ecommerce", max_tokens=2048)
"""
from __future__ import annotations

from langchain_openai import ChatOpenAI

from src.config import get_settings

# ── Model alias → proxy model name (defined in litellm_config.yaml) ──────────
_ROLE_MODEL: dict[str, str] = {
    "director":    "alpha/director",      # claude-opus-4-8
    "ecommerce":   "alpha/worker-smart",  # claude-sonnet-4-6
    "marketing":   "alpha/worker-smart",  # claude-sonnet-4-6
    "scraper":     "alpha/worker-fast",   # claude-haiku-4-5-20251001
    "fulfillment": "alpha/worker-fast",   # claude-haiku-4-5-20251001
}

# ── Sensible defaults per role ────────────────────────────────────────────────
_ROLE_DEFAULTS: dict[str, dict] = {
    "director":    {"temperature": 0.0, "max_tokens": 4096},
    "ecommerce":   {"temperature": 0.2, "max_tokens": 4096},
    "marketing":   {"temperature": 0.2, "max_tokens": 4096},
    "scraper":     {"temperature": 0.1, "max_tokens": 2048},
    "fulfillment": {"temperature": 0.0, "max_tokens": 2048},
}


def get_llm(
    role: str,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> ChatOpenAI:
    """
    Return a LangChain ChatOpenAI client routed through the LiteLLM proxy.

    Args:
        role:        Agent role key — one of director / ecommerce / marketing /
                     scraper / fulfillment.
        temperature: Override the role default (optional).
        max_tokens:  Override the role default (optional).

    The returned object is a drop-in replacement for ChatAnthropic:
        response = await llm.ainvoke([SystemMessage(...), HumanMessage(...)])
        llm_with_tools = llm.bind_tools([...])
    """
    settings = get_settings()

    model = _ROLE_MODEL.get(role, "alpha/worker-smart")
    defaults = _ROLE_DEFAULTS.get(role, {})

    return ChatOpenAI(
        model=model,
        base_url=settings.litellm_proxy_url,
        api_key=settings.litellm_master_key,
        temperature=temperature if temperature is not None else defaults.get("temperature", 0.2),
        max_tokens=max_tokens or defaults.get("max_tokens", 4096),
    )
