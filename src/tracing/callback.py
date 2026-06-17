from __future__ import annotations
import time
import logging
from typing import Any, List, Dict
from uuid import UUID
from datetime import datetime, timezone

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import BaseMessage
from langchain_core.outputs import LLMResult

from .store import trace_store
from .context import current_thread_id, current_node

logger = logging.getLogger(__name__)


class TraceCallback(BaseCallbackHandler):
    """Captures every LLM call: prompts, response, token counts, and timing."""

    def __init__(self):
        super().__init__()
        self._pending: dict[str, dict] = {}

    def on_chat_model_start(
        self,
        serialized: Dict[str, Any],
        messages: List[List[BaseMessage]],
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        thread_id = current_thread_id.get("")
        if not thread_id:
            return

        node = current_node.get("unknown")
        kw = serialized.get("kwargs", {})
        model = kw.get("model_name") or kw.get("model") or serialized.get("name", "unknown")

        system_prompt = ""
        user_parts: list[str] = []
        for msg_list in messages:
            for msg in msg_list:
                msg_type = getattr(msg, "type", "")
                content = str(msg.content) if hasattr(msg, "content") else ""
                if msg_type == "system":
                    system_prompt = content
                elif msg_type in ("human", "user"):
                    user_parts.append(content)
                elif msg_type == "ai":
                    user_parts.append(f"[prev assistant turn]: {content}")

        self._pending[str(run_id)] = {
            "thread_id": thread_id,
            "node": node,
            "model": model,
            "system_prompt": system_prompt,
            "user_prompt": "\n\n".join(user_parts),
            "started_ms": time.perf_counter() * 1000,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def on_llm_end(self, response: LLMResult, *, run_id: UUID, **kwargs: Any) -> None:
        pending = self._pending.pop(str(run_id), None)
        if not pending:
            return

        duration_ms = round(time.perf_counter() * 1000 - pending["started_ms"], 1)

        token_usage: dict = {}
        if response.llm_output:
            token_usage = response.llm_output.get("token_usage", {})

        response_text = ""
        if response.generations:
            gen = response.generations[0][0] if response.generations[0] else None
            if gen is not None:
                if hasattr(gen, "message"):
                    response_text = str(gen.message.content)
                else:
                    response_text = str(gen.text)

        # Use actual model name from response if we only have a placeholder
        actual_model = pending["model"]
        if response.llm_output:
            actual_model = response.llm_output.get("model_name", actual_model) or actual_model

        trace_store.add_llm_call(
            thread_id=pending["thread_id"],
            node=pending["node"],
            model=actual_model,
            system_prompt=pending["system_prompt"],
            user_prompt=pending["user_prompt"],
            response=response_text,
            input_tokens=token_usage.get("prompt_tokens", 0),
            output_tokens=token_usage.get("completion_tokens", 0),
            cache_read_tokens=token_usage.get("cache_read_input_tokens", 0),
            cache_write_tokens=token_usage.get("cache_creation_input_tokens", 0),
            duration_ms=duration_ms,
            timestamp=pending["timestamp"],
        )

    def on_llm_error(
        self, error: BaseException, *, run_id: UUID, **kwargs: Any
    ) -> None:
        pending = self._pending.pop(str(run_id), None)
        if not pending:
            return

        duration_ms = round(time.perf_counter() * 1000 - pending["started_ms"], 1)
        trace_store.add_llm_call(
            thread_id=pending["thread_id"],
            node=pending["node"],
            model=pending["model"],
            system_prompt=pending["system_prompt"],
            user_prompt=pending["user_prompt"],
            response="",
            input_tokens=0,
            output_tokens=0,
            cache_read_tokens=0,
            cache_write_tokens=0,
            duration_ms=duration_ms,
            timestamp=pending["timestamp"],
            error=str(error),
        )
