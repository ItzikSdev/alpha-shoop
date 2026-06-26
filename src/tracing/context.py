from contextvars import ContextVar
from typing import Any

current_thread_id: ContextVar[str] = ContextVar("current_thread_id", default="")
current_node: ContextVar[str] = ContextVar("current_node", default="unknown")

# The active TraceCallback for this run. Previously LangGraph propagated
# config={"callbacks": [...]} down to every node's LLM calls automatically;
# without the graph, get_llm() reads this directly so every worker's
# llm.ainvoke() still gets traced without needing per-call-site changes.
current_trace_callback: ContextVar[Any] = ContextVar("current_trace_callback", default=None)
