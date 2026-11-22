import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from src.gate.evaluator import GateConfig, RiskGate
from src.gate.models import GateContext, OrderProposal, OrderSide, OrderType


class MutatedRiskGate_NoStopLossCheck(RiskGate):
    """Planted Bug: Developer accidentally removes the per-trade stop-loss risk check."""
    def _check_per_trade_risk(self, proposal: OrderProposal, context: GateContext) -> list[str]:
        return []  # Bug: check disabled


class MutatedRiskGate_NoKillSwitch(RiskGate):
    """Planted Bug: Developer accidentally ignores kill switch status."""
    def _check_kill_switch_and_mode(self, context: GateContext) -> list[str]:
        return []  # Bug: check disabled


class MutatedRiskGate_NoFreshnessCheck(RiskGate):
    """Planted Bug: Developer accidentally comments out data freshness check."""
    def _check_freshness_and_reconciliation(self, context: GateContext) -> list[str]:
        return []  # Bug: check disabled


class MutatedRiskGate_50PercentPositionLimit(RiskGate):
    """Planted Bug: Developer changes position limit from 10% to 50%."""
    def __init__(self, config: GateConfig) -> None:
        mutated_config = config.model_copy(update={"max_position_pct": Decimal("0.50")})
        super().__init__(config=mutated_config)


@pytest.fixture
def context_and_excessive_risk_order() -> tuple[GateContext, OrderProposal]:
    now = datetime(2026, 11, 22, 12, 0, 0, tzinfo=UTC)
    context = GateContext(
        account_equity=Decimal("10000.00"),
        peak_equity=Decimal("10000.00"),
        daily_realized_loss=Decimal("0.00"),
        open_positions={},
        open_position_notionals={},
        orders_today_count=0,
        allowed_instruments={"BTC/USDT"},
        last_price=Decimal("30000.00"),
        last_bar_ts=now - timedelta(minutes=15),
        current_ts=now,
        bar_interval=timedelta(hours=4),
        kill_switch_active=False,
        used_idempotency_keys=set(),
        mode="PAPER"
    )
    # 5% risk trade: $500 risk on $10,000 equity (max allowed is 1% / $100)
    proposal = OrderProposal(
        proposal_id=uuid.uuid4(),
        idempotency_key=uuid.uuid4(),
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        price=Decimal("30000.00"),
        size=Decimal("0.033"),
        stop_loss=Decimal("15000.00"),  # $15,000 distance * 0.033 = ~$495 risk
        take_profit=Decimal("35000.00"),
        rationale_id="TEST"
    )
    return context, proposal


def test_planted_bug_catches_disabled_stop_loss_check(
    context_and_excessive_risk_order: tuple[GateContext, OrderProposal]
) -> None:
    """Verify that removing the stop-loss check is caught as a defect."""
    context, proposal = context_and_excessive_risk_order
    config = GateConfig()

    # The authentic gate MUST reject the excessive risk order
    authentic_gate = RiskGate(config=config)
    assert authentic_gate.evaluate(proposal, context).passed is False

    # The mutated gate allows the dangerous order (demonstrating the planted bug)
    buggy_gate = MutatedRiskGate_NoStopLossCheck(config=config)
    assert buggy_gate.evaluate(proposal, context).passed is True


def test_planted_bug_catches_ignored_kill_switch(
    context_and_excessive_risk_order: tuple[GateContext, OrderProposal]
) -> None:
    """Verify that ignoring kill switch status is caught as a defect."""
    context, proposal = context_and_excessive_risk_order
    context.kill_switch_active = True
    config = GateConfig()

    authentic_gate = RiskGate(config=config)
    assert authentic_gate.evaluate(proposal, context).passed is False

    buggy_gate = MutatedRiskGate_NoKillSwitch(config=config)
    # The buggy gate bypassed kill switch
    assert not any("kill switch" in r.lower() for r in buggy_gate.evaluate(proposal, context).reasons)


def test_planted_bug_catches_ignored_stale_data(
    context_and_excessive_risk_order: tuple[GateContext, OrderProposal]
) -> None:
    """Verify that ignoring stale data check is caught as a defect."""
    context, proposal = context_and_excessive_risk_order
    context.last_bar_ts = context.current_ts - timedelta(hours=24)  # Very stale
    config = GateConfig()

    authentic_gate = RiskGate(config=config)
    assert authentic_gate.evaluate(proposal, context).passed is False

    buggy_gate = MutatedRiskGate_NoFreshnessCheck(config=config)
    assert not any("stale" in r.lower() for r in buggy_gate.evaluate(proposal, context).reasons)
