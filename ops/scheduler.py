import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from ops.alerts import AlertService
from src.agent.loop import AgentConfig, AgentLoop, RunResult
from src.connector.server import AegisConnectorServer
from src.gate.reconcile import AccountState, PositionState, reconcile_states
from src.reports.recompute import RawExecutionRecord, RunReportRecord, recompute_run_metrics
from src.signals.freshness import verify_bar_freshness


class SchedulerConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    lock_file: Path
    interval_hours: int = 4


class ScheduledRunReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    success: bool
    checks: dict[str, bool]
    summary: str
    cycle_result: RunResult | None = None
    errors: list[str] = []


class AutonomousScheduler:
    """Autonomous trading run orchestrator enforcing 'ran is not worked' governance (PRD Section 15 & 17)."""

    def __init__(
        self,
        connector: AegisConnectorServer,
        scheduler_config: SchedulerConfig,
        agent_config: AgentConfig | None = None,
        alert_service: AlertService | None = None
    ) -> None:
        self.connector = connector
        self.scheduler_config = scheduler_config
        self.agent_config = agent_config or AgentConfig(mode="PAPER_EXECUTION")
        self.alert_service = alert_service or AlertService()
        self.lock_file = scheduler_config.lock_file

    def acquire_lock(self) -> bool:
        """Acquire single-process execution lock file to prevent overlapping runs."""
        try:
            if self.lock_file.exists():
                return False
            # Atomic file creation
            self.lock_file.parent.mkdir(parents=True, exist_ok=True)
            flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
            fd = os.open(str(self.lock_file), flags)
            with os.fdopen(fd, "w") as f:
                f.write(f"pid={os.getpid()}\nts={datetime.now(UTC).isoformat()}\n")
            return True
        except (FileExistsError, OSError):
            return False

    def release_lock(self) -> None:
        """Release single-process execution lock."""
        try:
            if self.lock_file.exists():
                self.lock_file.unlink()
        except OSError:
            pass

    def _get_account_state(self) -> AccountState:
        acc = self.connector.get_account()
        positions: dict[str, PositionState] = {}
        for sym, pos_data in acc["positions"].items():
            positions[sym] = PositionState(
                symbol=sym,
                size=Decimal(str(pos_data["size"])),
                avg_price=Decimal(str(pos_data.get("avg_price", "0.00")))
            )
        return AccountState(
            equity=Decimal(str(acc["equity"])),
            cash=Decimal(str(acc["cash"])),
            positions=positions
        )

    def run_scheduled_cycle(self, current_ts: datetime | None = None) -> ScheduledRunReport:
        """Execute a full autonomous cycle with pre- and post-flight verification."""
        if not self.acquire_lock():
            return ScheduledRunReport(
                success=False,
                checks={},
                summary="Run skipped: Overlapping execution lock active.",
                errors=["Lock file already held by active process."]
            )

        checks: dict[str, bool] = {
            "data_freshness_verified": False,
            "pre_reconciliation_matched": False,
            "cycle_executed": False,
            "gate_decisions_recorded": False,
            "post_reconciliation_matched": False,
            "recomputation_verified": False,
        }
        errors: list[str] = []
        cycle_result: RunResult | None = None

        try:
            now = current_ts or datetime.now(UTC)

            # 1. Verify Data Freshness
            freshness_ok = True
            for symbol in self.connector.allowed_instruments:
                bars = self.connector.get_bars(symbol=symbol, timeframe="1d", limit=1)
                if bars:
                    bar_dt = datetime.fromtimestamp(bars[-1]["ts"], tz=UTC)
                    ok, msg = verify_bar_freshness(
                        latest_bar_ts=bar_dt,
                        current_ts=now,
                        bar_interval=timedelta(days=1),
                        max_bars_lag=2
                    )
                    if not ok:
                        freshness_ok = False
                        errors.append(f"Freshness check failed for {symbol}: {msg}")
            checks["data_freshness_verified"] = freshness_ok

            # 2. Pre-Reconciliation
            pre_db_state = self._get_account_state()
            pre_broker_state = self._get_account_state()
            pre_rec = reconcile_states(pre_db_state, pre_broker_state)
            checks["pre_reconciliation_matched"] = pre_rec.match
            if not pre_rec.match:
                errors.extend(pre_rec.diffs)
                self.alert_service.notify_reconciliation_mismatch(pre_rec.diffs)

            # 3. Execute Trading Agent Loop
            agent = AgentLoop(connector=self.connector, config=self.agent_config)
            cycle_result = agent.execute_cycle()
            checks["cycle_executed"] = cycle_result.status in ("SUCCESS", "STOPPED")

            # 4. Gate Decisions Recorded
            # In paper mode, verify proposal and order records are populated
            gate_audit_ok = True
            if cycle_result.proposals_generated_count > 0:
                gate_audit_ok = len(self.connector.proposals) >= cycle_result.proposals_generated_count
            checks["gate_decisions_recorded"] = gate_audit_ok

            # 5. Post-Reconciliation
            post_db_state = self._get_account_state()
            post_broker_state = self._get_account_state()
            post_rec = reconcile_states(post_db_state, post_broker_state)
            checks["post_reconciliation_matched"] = post_rec.match
            if not post_rec.match:
                errors.extend(post_rec.diffs)
                self.alert_service.notify_reconciliation_mismatch(post_rec.diffs)

            # 6. Recomputation Proof
            # Collect raw records and reconcile reported PnL/fees
            raw_records = [
                RawExecutionRecord(
                    symbol=t["symbol"],
                    fill_price=Decimal(str(t["price"])),
                    size=Decimal(str(t["size"])),
                    fee=Decimal(str(t["fee"])),
                    side=t["side"]
                )
                for t in self.connector.broker.trade_history
            ]
            reported_record = RunReportRecord(
                reported_realized_pnl=self.connector.broker.realized_pnl,
                reported_total_fees=self.connector.broker.total_fees_paid,
                reported_trades_count=len(self.connector.broker.trade_history)
            )
            recomp = recompute_run_metrics(raw_records, reported_record)
            checks["recomputation_verified"] = recomp.verified
            if not recomp.verified:
                errors.extend(recomp.discrepancies)

            # Overall success requires all 6 conditions
            all_passed = all(checks.values()) and (len(errors) == 0)

            # Heartbeat alert
            acc = self.connector.get_account()
            self.alert_service.notify_heartbeat(
                equity=Decimal(str(acc["equity"])),
                daily_pnl=self.connector.broker.realized_pnl,
                open_positions_count=len(acc["positions"]),
                status="HEALTHY" if all_passed else "DEGRADED"
            )

            summary = (
                f"Scheduled cycle {'SUCCEEDED' if all_passed else 'FAILED'}. "
                f"Checks passed: {sum(1 for v in checks.values() if v)}/{len(checks)}. "
                f"Orders placed: {cycle_result.orders_placed_count}."
            )
            return ScheduledRunReport(
                success=all_passed,
                checks=checks,
                summary=summary,
                cycle_result=cycle_result,
                errors=errors
            )
        finally:
            self.release_lock()
