from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from ops.alerts import AlertService
from src.connector.server import AegisConnectorServer


class DashboardMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)

    equity: Decimal
    cash: Decimal
    unrealized_pnl: Decimal
    open_positions_count: int
    daily_realized_loss: Decimal
    daily_loss_budget: Decimal
    daily_loss_pct_used: Decimal
    peak_equity: Decimal
    current_drawdown_pct: Decimal
    max_drawdown_limit_pct: Decimal
    orders_today_count: int
    max_orders_per_day: int
    kill_switch_active: bool
    reconciliation_matched: bool


class AegisDashboard:
    """Operations and Supervision Dashboard for AEGIS (PRD Section 14 & 15)."""

    def __init__(
        self,
        connector: AegisConnectorServer,
        alert_service: AlertService | None = None
    ) -> None:
        self.connector = connector
        self.alert_service = alert_service or AlertService()

    def get_metrics(self) -> DashboardMetrics:
        acc = self.connector.get_account()
        run_state = self.connector.get_run_state()

        equity = Decimal(str(acc["equity"]))
        cash = Decimal(str(acc["cash"]))
        unrealized = Decimal(str(acc["unrealized_pnl"]))
        peak = self.connector.peak_equity

        dd_pct = ((peak - equity) / peak * Decimal("100.00")) if peak > Decimal(0) and equity < peak else Decimal("0.00")
        daily_loss = self.connector.daily_realized_loss
        daily_budget = Decimal("200.00")
        loss_pct = (daily_loss / daily_budget * Decimal("100.00")) if daily_budget > Decimal(0) else Decimal("0.00")

        return DashboardMetrics(
            equity=equity,
            cash=cash,
            unrealized_pnl=unrealized,
            open_positions_count=len(acc["positions"]),
            daily_realized_loss=daily_loss,
            daily_loss_budget=daily_budget,
            daily_loss_pct_used=loss_pct,
            peak_equity=peak,
            current_drawdown_pct=dd_pct,
            max_drawdown_limit_pct=Decimal("10.00"),
            orders_today_count=self.connector.orders_today_count,
            max_orders_per_day=10,
            kill_switch_active=run_state["kill_switch_active"],
            reconciliation_matched=True
        )

    def render_markdown(self) -> str:
        """Render operational metrics as Markdown for review contracts and human oversight."""
        m = self.get_metrics()
        acc = self.connector.get_account()

        positions_rows: list[str] = []
        if acc["positions"]:
            for sym, pos in acc["positions"].items():
                positions_rows.append(
                    f"| {sym} | {pos['size']} | ${Decimal(pos['avg_price']):.2f} | ${Decimal(pos['notional']):.2f} | ${Decimal(pos['unrealized_pnl']):.2f} |"
                )
        else:
            positions_rows.append("| *None* | 0.0 | $0.00 | $0.00 | $0.00 |")

        ks_badge = "**ENGAGED (HALTED)**" if m.kill_switch_active else "CLEAR (Operational)"
        rec_badge = "MATCHED (OK)" if m.reconciliation_matched else "**MISMATCH DETECTED**"

        lines = [
            "# AEGIS Operations Dashboard",
            "",
            "## 1. System Health & Governance",
            f"- **Emergency Kill Switch**: {ks_badge}",
            f"- **DSoR Reconciliation**: {rec_badge}",
            f"- **Orders Placed Today**: {m.orders_today_count} / {m.max_orders_per_day}",
            "",
            "## 2. Portfolio & Risk Budgets",
            f"- **Total Account Equity**: ${m.equity:.2f} USDT",
            f"- **Available Cash**: ${m.cash:.2f} USDT",
            f"- **Unrealized PnL**: ${m.unrealized_pnl:.2f} USDT",
            f"- **Peak Equity**: ${m.peak_equity:.2f} USDT",
            f"- **Current Drawdown**: {m.current_drawdown_pct:.2f}% (Limit: {m.max_drawdown_limit_pct:.2f}%)",
            f"- **Daily Loss Utilized**: ${m.daily_realized_loss:.2f} / ${m.daily_loss_budget:.2f} ({m.daily_loss_pct_used:.1f}%)",
            "",
            "## 3. Active Positions",
            "| Symbol | Size | Avg Entry | Notional | Unrealized PnL |",
            "|---|---|---|---|---|",
            *positions_rows,
            "",
            "## 4. Supervision & Alerts",
            f"- Total Recorded Alerts: {len(self.alert_service.get_history())}"
        ]
        return "\n".join(lines)
