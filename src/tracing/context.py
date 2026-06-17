from contextvars import ContextVar

current_thread_id: ContextVar[str] = ContextVar("current_thread_id", default="")
current_node: ContextVar[str] = ContextVar("current_node", default="unknown")
