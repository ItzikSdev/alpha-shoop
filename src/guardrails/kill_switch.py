"""Budget kill-switch — hard limits on ad spend and order values."""
from __future__ import annotations
import threading
from datetime import datetime, date


class KillSwitch:
    """
    Singleton kill-switch. Once activated, all new agent runs are blocked.
    Thread-safe; designed to be checked in every agent iteration.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active = False
        self._reason: str = ""
        self._operator: str = ""
        self._activated_at: datetime | None = None
        self._daily_spend: dict[date, float] = {}

    @property
    def is_active(self) -> bool:
        with self._lock:
            return self._active

    def activate(self, reason: str, operator: str) -> bool:
        with self._lock:
            self._active = True
            self._reason = reason
            self._operator = operator
            self._activated_at = datetime.utcnow()
            return True

    def reset(self, operator: str) -> None:
        with self._lock:
            self._active = False
            self._reason = ""
            self._operator = operator

    def record_spend(self, amount_usd: float, max_daily_usd: float) -> None:
        """Track daily ad spend. Raises if limit exceeded."""
        today = date.today()
        with self._lock:
            self._daily_spend[today] = self._daily_spend.get(today, 0.0) + amount_usd
            if self._daily_spend[today] > max_daily_usd:
                self._active = True
                self._reason = (
                    f"Daily ad spend ${self._daily_spend[today]:.2f} "
                    f"exceeds HARDCODED limit ${max_daily_usd:.2f}"
                )
                raise ValueError(self._reason)

    @property
    def state(self) -> dict:
        with self._lock:
            return {
                "active": self._active,
                "reason": self._reason,
                "operator": self._operator,
                "activated_at": self._activated_at.isoformat() if self._activated_at else None,
            }
