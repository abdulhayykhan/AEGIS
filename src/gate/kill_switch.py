import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict

DEFAULT_LOCK_FILE = Path("data/aegis_kill_switch.lock")
AUTHORIZED_OPERATORS = {"Abdul Hayy", "abdulhayykhan", "OWNER"}


class KillSwitchState(BaseModel):
    model_config = ConfigDict(frozen=True)

    engaged: bool
    reason: str
    engaged_by: str
    timestamp: datetime


class StandaloneKillSwitch:
    """Out-of-band kill switch that operates independently of whether the agent is running."""

    def __init__(self, lock_file_path: Path = DEFAULT_LOCK_FILE) -> None:
        self.lock_file_path = lock_file_path

    def is_engaged(self) -> bool:
        return self.lock_file_path.exists()

    def engage(self, reason: str, operator: str = "Abdul Hayy") -> None:
        self.lock_file_path.parent.mkdir(parents=True, exist_ok=True)
        state = KillSwitchState(
            engaged=True,
            reason=reason,
            engaged_by=operator,
            timestamp=datetime.now(UTC)
        )
        self.lock_file_path.write_text(state.model_dump_json(indent=2), encoding="utf-8")

    def disengage(self, operator: str) -> None:
        """Clear kill switch. Programmatically forbidden to AI agents."""
        if operator not in AUTHORIZED_OPERATORS:
            raise PermissionError(f"Unauthorized operator '{operator}' cannot disengage the Kill Switch.")

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
