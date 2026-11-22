import json
import os
import urllib.request
from datetime import UTC, datetime, timedelta
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

    def __init__(
        self,
        telegram_token: str | None = None,
        chat_id: str | None = None,
        heartbeat_url: str | None = None
    ) -> None:
        self.telegram_token = telegram_token
        self.chat_id = chat_id
        self.heartbeat_url = (
            heartbeat_url
            or os.environ.get("AEGIS_HEARTBEAT_WEBHOOK_URL")
            or os.environ.get("DEAD_MANS_SWITCH_WEBHOOK_URL")
        )
        self._history: list[AlertMessage] = []

    def ping_external_heartbeat(self, status: str = "success", message: str = "") -> None:
        """Ping external dead-man's switch monitoring service (e.g. Healthchecks.io / Cronitor).
        
        Guarantees PRD Section 15.3 & Review Finding H7.
        """
        if not self.heartbeat_url:
            return
        url = self.heartbeat_url.rstrip("/")
        if status == "fail":
            url = f"{url}/fail"
        try:
            payload = message.encode("utf-8") if message else None
            req = urllib.request.Request(url, data=payload, headers={"User-Agent": "AEGIS-DeadMansSwitch/1.0"})
            urllib.request.urlopen(req, timeout=5)
        except (urllib.error.URLError, TimeoutError, OSError):
            pass

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
        token = self.telegram_token or os.environ.get("AEGIS_TELEGRAM_BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN")
        chat_id = self.chat_id or os.environ.get("AEGIS_TELEGRAM_CHAT_ID") or os.environ.get("TELEGRAM_CHAT_ID")
        if not token or not chat_id:
            return
        try:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = json.dumps({
                "chat_id": chat_id,
                "text": f"[{msg.level.value}] {msg.text}"
            }).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"}
            )
            urllib.request.urlopen(req, timeout=5)
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
            pass

    def check_dead_mans_switch(
        self,
        last_heartbeat: datetime,
        max_interval: timedelta = timedelta(hours=6)
    ) -> bool:
        """Verify that heartbeat was received within the maximum allowed window (PRD 15.3).
        
        Returns False and triggers a critical supervisor alert if overdue.
        """
        elapsed = datetime.now(UTC) - last_heartbeat
        if elapsed > max_interval:
            self._record(
                AlertLevel.CRITICAL,
                f"[DEAD-MAN'S SWITCH] OVERDUE HEARTBEAT: Last heartbeat was {elapsed.total_seconds() / 3600:.1f}h ago "
                f"(threshold: {max_interval.total_seconds() / 3600:.1f}h). Halting automated runs."
            )
            return False
        return True

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

    def notify_emergency_flatten(
        self,
        operator: str,
        positions_flattened: int,
        details: str = ""
    ) -> AlertMessage:
        text = (
            f"[CRITICAL] EMERGENCY FLATTEN EXECUTED:\n"
            f"Operator: {operator}\n"
            f"Positions flattened: {positions_flattened}\n"
            f"{details}"
        )
        return self._record(AlertLevel.CRITICAL, text)

    def notify_demotion(
        self,
        old_rung: str,
        new_rung: str,
        reasons: list[str]
    ) -> AlertMessage:
        reason_str = "\n".join(f"- {r}" for r in reasons)
        text = (
            f"[CRITICAL] AUTONOMY RUNG DEMOTION TRIGGERED:\n"
            f"Demoting from {old_rung} to {new_rung}.\n"
            f"Reasons:\n{reason_str}\n"
            f"Execution halted. Owner review required before restoring authority."
        )
        return self._record(AlertLevel.CRITICAL, text)
