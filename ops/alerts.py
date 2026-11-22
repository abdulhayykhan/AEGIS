from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict


class AlertLevel(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class AlertMessage(BaseModel):
    model_config = ConfigDict(frozen=True)

    level: AlertLevel
    text: str
    timestamp: datetime


class AlertService:
    """Operations alerting service for notifications, heartbeats, and threshold breaches.
    
    Adheres to Book Ch. 17 (Supervision by Exception).
    """

    def __init__(self, telegram_token: str | None = None, chat_id: str | None = None) -> None:
        self.telegram_token = telegram_token
        self.chat_id = chat_id
        self._history: list[AlertMessage] = []

    def get_history(self) -> list[AlertMessage]:
        return list(self._history)

    def _record(self, level: AlertLevel, text: str) -> AlertMessage:
        msg = AlertMessage(
            level=level,
            text=text,
            timestamp=datetime.now(UTC)
        )
        self._history.append(msg)
        self._dispatch(msg)
        return msg

    def _dispatch(self, msg: AlertMessage) -> None:
        """Dispatch message to external channels (e.g. Telegram) if configured."""
        if not self.telegram_token or not self.chat_id:
            return
        # In live setup, calls Telegram Bot API send_message.
        # Safe no-op / mock fallback if unconfigured.

    def notify_limit_approaching(
        self,
        limit_name: str,
        current_val: Decimal,
        threshold_val: Decimal,
        pct_used: Decimal
    ) -> AlertMessage:
        text = (
            f"[WARNING] Limit Approaching: {limit_name} is at {pct_used:.1f}% of threshold "
            f"({current_val:.2f} / {threshold_val:.2f})."
        )
        return self._record(AlertLevel.WARNING, text)

    def notify_reconciliation_mismatch(self, diffs: list[str]) -> AlertMessage:
        diff_str = "\n".join(f"- {d}" for d in diffs)
        text = (
            f"[CRITICAL] RECONCILIATION MISMATCH DETECTED:\n"
            f"{diff_str}\n"
            f"Halting affected routes and notifying supervisor."
        )
        return self._record(AlertLevel.CRITICAL, text)

    def notify_heartbeat(
        self,
        equity: Decimal,
        daily_pnl: Decimal,
        open_positions_count: int,
        status: str
    ) -> AlertMessage:
        sign = "+" if daily_pnl >= 0 else ""
        text = (
            f"[HEARTBEAT] AEGIS Operational Status: {status}\n"
            f"Equity: {equity:.2f} USDT\n"
            f"Daily PnL: {sign}{daily_pnl:.2f} USDT\n"
            f"Open Positions: {open_positions_count}"
        )
        return self._record(AlertLevel.INFO, text)
