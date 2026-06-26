from .store import trace_store
from .callback import TraceCallback
from .context import current_thread_id, current_node, current_trace_callback


def agent_log(msg: str, level: str = "info") -> None:
    """Log a structured message from within an agent node. Reads context vars automatically."""
    tid = current_thread_id.get("")
    node = current_node.get("unknown")
    if tid:
        trace_store.add_log(tid, node=node, msg=msg, level=level)


__all__ = [
    "trace_store", "TraceCallback", "current_thread_id", "current_node",
    "current_trace_callback", "agent_log",
]
