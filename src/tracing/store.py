from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class LogEntry:
    ts: str
    node: str
    msg: str
    level: str  # info | action | success | error | warning

    def to_dict(self) -> dict:
        return {"ts": self.ts, "node": self.node, "msg": self.msg, "level": self.level}


@dataclass
class LLMCallTrace:
    id: int
    node: str
    model: str
    system_prompt: str
    user_prompt: str
    response: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    duration_ms: float
    timestamp: str
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "node": self.node,
            "model": self.model,
            "system_prompt": self.system_prompt,
            "user_prompt": self.user_prompt,
            "response": self.response,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "cache_write_tokens": self.cache_write_tokens,
            "total_tokens": self.input_tokens + self.output_tokens,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp,
            "error": self.error,
        }


@dataclass
class RunTrace:
    thread_id: str
    task: str
    operator: str
    status: str
    started_at: str
    finished_at: Optional[str]
    llm_calls: list[LLMCallTrace] = field(default_factory=list)
    logs: list[LogEntry] = field(default_factory=list)
    _call_counter: int = field(default=0, repr=False)

    def add_call(self, **kwargs) -> LLMCallTrace:
        self._call_counter += 1
        call = LLMCallTrace(id=self._call_counter, **kwargs)
        self.llm_calls.append(call)
        return call

    def add_log(self, node: str, msg: str, level: str = "info") -> LogEntry:
        entry = LogEntry(
            ts=datetime.now(timezone.utc).isoformat(),
            node=node,
            msg=msg,
            level=level,
        )
        self.logs.append(entry)
        return entry

    @property
    def total_input_tokens(self) -> int:
        return sum(c.input_tokens for c in self.llm_calls)

    @property
    def total_output_tokens(self) -> int:
        return sum(c.output_tokens for c in self.llm_calls)

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens

    def to_summary(self) -> dict:
        return {
            "thread_id": self.thread_id,
            "task": self.task,
            "operator": self.operator,
            "status": self.status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "total_llm_calls": len(self.llm_calls),
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_tokens,
        }

    def to_dict(self) -> dict:
        return {
            **self.to_summary(),
            "llm_calls": [c.to_dict() for c in self.llm_calls],
            "logs": [e.to_dict() for e in self.logs],
        }


class TraceStore:
    def __init__(self):
        self._runs: dict[str, RunTrace] = {}

    def start_run(self, thread_id: str, task: str, operator: str) -> RunTrace:
        run = RunTrace(
            thread_id=thread_id,
            task=task,
            operator=operator,
            status="running",
            started_at=datetime.now(timezone.utc).isoformat(),
            finished_at=None,
        )
        self._runs[thread_id] = run
        return run

    def get_run(self, thread_id: str) -> Optional[RunTrace]:
        return self._runs.get(thread_id)

    def finish_run(self, thread_id: str, status: str) -> None:
        run = self._runs.get(thread_id)
        if run:
            run.status = status
            run.finished_at = datetime.now(timezone.utc).isoformat()

    def list_runs(self) -> list[RunTrace]:
        return sorted(self._runs.values(), key=lambda r: r.started_at, reverse=True)

    def add_llm_call(self, thread_id: str, **kwargs) -> Optional[LLMCallTrace]:
        run = self._runs.get(thread_id)
        if run:
            return run.add_call(**kwargs)
        return None

    def add_log(self, thread_id: str, node: str, msg: str, level: str = "info") -> None:
        run = self._runs.get(thread_id)
        if run:
            run.add_log(node=node, msg=msg, level=level)


trace_store = TraceStore()
