import json
import os
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict

DEFAULT_LOCK_FILE = Path("data/aegis_kill_switch.lock")
AUTHORIZED_OPERATORS = {"Abdul Hayy", "Abdul Hayy Khan", "abdulhayykhan", "OWNER"}


def get_default_lock_file() -> Path:
    env_path = os.environ.get("AEGIS_KILL_SWITCH_LOCK")
    return Path(env_path) if env_path else DEFAULT_LOCK_FILE


class KillSwitchState(BaseModel):
    model_config = ConfigDict(frozen=True)

    engaged: bool
    reason: str
    engaged_by: str
    timestamp: datetime


class StandaloneKillSwitch:
    """Out-of-band kill switch that operates independently of whether the agent is running."""

    def __init__(self, lock_file_path: Path | None = None) -> None:
        self.lock_file_path = lock_file_path or get_default_lock_file()

    def is_engaged(self) -> bool:
        if not self.lock_file_path.exists():
            return False
        try:
            data = json.loads(self.lock_file_path.read_text(encoding="utf-8"))
            return bool(data.get("engaged", True))
        except Exception:  # noqa: BLE001
            # Corrupt, locked, or unreadable lock file must be treated as engaged (fail-safe)
            return True

    def engage(self, reason: str, operator: str = "Abdul Hayy") -> None:
        self.lock_file_path.parent.mkdir(parents=True, exist_ok=True)
        state = KillSwitchState(
            engaged=True,
            reason=reason,
            engaged_by=operator,
            timestamp=datetime.now(UTC)
        )
        self.lock_file_path.write_text(state.model_dump_json(indent=2), encoding="utf-8")

    def disengage(self, operator: str, token: str | None = None) -> None:
        """Clear kill switch. Programmatically forbidden to AI agents (B4 & Proof 8)."""
        import hmac

        if operator not in AUTHORIZED_OPERATORS:
            raise PermissionError(f"Unauthorized operator '{operator}' cannot disengage the Kill Switch.")

        env_token = os.environ.get("AEGIS_OWNER_SECRET") or os.environ.get("AEGIS_OWNER_TOKEN")
        if not env_token:
            raise PermissionError("AEGIS_OWNER_SECRET environment variable is not configured. Cannot disengage Kill Switch.")

        if not token or not hmac.compare_digest(token, env_token):
            raise PermissionError("Invalid owner security token for kill switch disengagement.")

        if self.lock_file_path.exists():
            self.lock_file_path.unlink()

    def get_status(self) -> KillSwitchState:
        if not self.lock_file_path.exists():
            return KillSwitchState(
                engaged=False,
                reason="System normal",
                engaged_by="NONE",
                timestamp=datetime.now(UTC)
            )
        try:
            data = json.loads(self.lock_file_path.read_text(encoding="utf-8"))
            return KillSwitchState(**data)
        except (json.JSONDecodeError, OSError, ValueError):
            return KillSwitchState(

                engaged=True,
                reason="Corrupt or manual lock file detected",
                engaged_by="UNKNOWN",
                timestamp=datetime.now(UTC)
            )
