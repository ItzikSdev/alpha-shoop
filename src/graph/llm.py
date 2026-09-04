"""
Local-Qwen3 LLM helper for the graph-orchestration work (src/graph/).

`get_graph_llm()` wraps `src.llm.client.get_llm("standup", ...)`, which
already resolves unconditionally to the `alpha/local-fast` LiteLLM alias →
`ollama_chat/qwen3:14b` (see litellm_config.yaml) — a plain ChatOpenAI
pointed at the local LiteLLM proxy, not Anthropic. Callers here go through
this wrapper instead of `get_llm` directly so a future change to what the
`standup` role resolves to (e.g. if it's ever repointed at a hosted model for
unrelated org-chat reasons) doesn't silently change what this pipeline runs
on — graph nodes are meant to always be free, local, and 100% off the
Anthropic budget, not "usually local because standup happens to be today."

Pydantic schemas for tool calling: Qwen3 14B (like most local/smaller
models) is more reliable at picking the right tool + arguments when the
schema is explicit and well-described, rather than relying on LangChain's
implicit signature-based schema generation (the style used by the plain
`@tool`-decorated functions in src.org.agent_loop). Prefer:

    from pydantic import BaseModel, Field
    from langchain_core.tools import tool

    class MyToolArgs(BaseModel):
        query: str = Field(description="What to search for.")
        limit: int = Field(default=5, description="Max results to return.")

    @tool(args_schema=MyToolArgs)
    async def my_tool(query: str, limit: int = 5) -> dict:
        \"\"\"One-line description of what this tool does.\"\"\"
        ...

    llm = get_graph_llm().bind_tools([my_tool])
"""
from __future__ import annotations

from langchain_openai import ChatOpenAI

from src.llm.client import get_llm


def get_graph_llm(
    temperature: float = 0.3,
    max_tokens: int | None = None,
    timeout: int | None = None,
) -> ChatOpenAI:
    """Local Qwen3 14B via the LiteLLM proxy — always, regardless of
    ORG_LOCAL_LLM/budget state (those exist to reroute *other* roles away
    from Anthropic on overage; this pipeline never touches Anthropic)."""
    return get_llm("standup", temperature=temperature, max_tokens=max_tokens, timeout=timeout)
