"""
LiteLLM proxy client factory.

Every agent gets its LLM from here — one line, no model IDs in agent code.
The proxy at LITELLM_PROXY_URL maps aliases → real Anthropic models and
handles retries, cost tracking, and future model swaps transparently.

Usage:
    from src.llm import get_llm

    llm = get_llm("scraper",  temperature=0.0)   # ChatOpenAI → proxy → claude-haiku-4-5
    llm = get_llm("ecommerce", max_tokens=2048)
"""
from __future__ import annotations

import os

from langchain_openai import ChatOpenAI

from src.config import get_settings
from src.tracing.context import current_trace_callback

# ── Model alias → proxy model name (defined in litellm_config.yaml) ──────────
# No "director" role: src/agents/director.py was deleted (replaced by
# orchestrator.py's plain Python control flow) and nothing calls get_llm()
# with that role anymore.
#
# Org roles:
#   - "executive": leadership reasoning (strategy/retro) → worker-smart (Sonnet)
#   - "standup":   frequent/cheap org calls (standups, onboarding, training) →
#                  local Ollama via the alpha/local-fast alias (free). Falls
#                  back to worker-fast if that alias isn't configured.
_ROLE_MODEL: dict[str, str] = {
    "ecommerce":   "alpha/worker-smart",  # claude-sonnet-4-6
    "marketing":   "alpha/worker-smart",  # claude-sonnet-4-6
    "scraper":     "alpha/worker-fast",   # claude-haiku-4-5-20251001
    "fulfillment": "alpha/worker-fast",   # claude-haiku-4-5-20251001
    "executive":   "alpha/worker-smart",  # claude-sonnet-4-6 — company strategy
    "standup":     "alpha/local-fast",    # local Ollama 7B — frequent, ~free
    "developer":   "alpha/local-coder",   # local Ollama 14B coder — Grace
}

# ── Sensible defaults per role ────────────────────────────────────────────────
_ROLE_DEFAULTS: dict[str, dict] = {
    "ecommerce":   {"temperature": 0.2, "max_tokens": 4096},
    "marketing":   {"temperature": 0.2, "max_tokens": 4096},
    "scraper":     {"temperature": 0.1, "max_tokens": 2048},
    "fulfillment": {"temperature": 0.0, "max_tokens": 2048},
    "executive":   {"temperature": 0.5, "max_tokens": 3072},
    "standup":     {"temperature": 0.5, "max_tokens": 2048},
    "developer":   {"temperature": 0.3, "max_tokens": 4096},
}

# Org roles that the ORG_LOCAL_LLM=1 toggle reroutes to the local model to save
# tokens (at the cost of quality on strategy reasoning).
_ORG_ROLES = {"executive", "standup"}
_LOCAL_ALIAS = "alpha/local-fast"


def get_llm(
    role: str,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> ChatOpenAI:
    """
    Return a LangChain ChatOpenAI client routed through the LiteLLM proxy.

    Args:
        role:        Agent role key — one of ecommerce / marketing / scraper /
                     fulfillment.
        temperature: Override the role default (optional).
        max_tokens:  Override the role default (optional).

    The returned object is a drop-in replacement for ChatAnthropic:
        response = await llm.ainvoke([SystemMessage(...), HumanMessage(...)])
        llm_with_tools = llm.bind_tools([...])
    """
    settings = get_settings()

    model = _ROLE_MODEL.get(role, "alpha/worker-smart")
    # Cost guardrails for org reasoning: route to the FREE local model when the
    # operator opts in OR the monthly Claude budget cap ($100) is reached — so
    # the company keeps running without ever exceeding the budget.
    if role in _ORG_ROLES:
        force_local = os.environ.get("ORG_LOCAL_LLM") in ("1", "true", "True")
        if not force_local:
            try:
                from src.budget import over_budget
                force_local = over_budget()
            except Exception:
                force_local = False
        if force_local:
            model = _LOCAL_ALIAS
    defaults = _ROLE_DEFAULTS.get(role, {})

    callback = current_trace_callback.get(None)

    return ChatOpenAI(
        model=model,
        base_url=settings.litellm_proxy_url,
        api_key=settings.litellm_master_key,
        temperature=temperature if temperature is not None else defaults.get("temperature", 0.2),
        max_tokens=max_tokens or defaults.get("max_tokens", 4096),
        # Never let a single call hang forever (a large design CSS generation
        # used to stall indefinitely with no timeout, freezing the whole run).
        timeout=180,
        max_retries=1,
        callbacks=[callback] if callback else None,
    )
