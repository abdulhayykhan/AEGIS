import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from src.gate.evaluator import GateConfig, RiskGate
from src.gate.models import GateContext, OrderProposal, OrderSide, OrderType


@settings(max_examples=100, deadline=None)
@given(
    equity=st.decimals(min_value=Decimal("500.00"), max_value=Decimal("500000.00"), places=2),
    entry_price=st.decimals(min_value=Decimal("10.00"), max_value=Decimal("100000.00"), places=2),
    stop_distance_pct=st.decimals(min_value=Decimal("0.005"), max_value=Decimal("0.20"), places=4),
    raw_size=st.decimals(min_value=Decimal("0.0001"), max_value=Decimal("500.00"), places=4),
)
def test_property_gate_never_violates_invariants(
    equity: Decimal,
    entry_price: Decimal,
    stop_distance_pct: Decimal,
    raw_size: Decimal
) -> None:
    """Hypothesis invariant: No accepted order ever violates the 1% risk or 10% position limit."""
    stop_loss = entry_price * (Decimal("1.0") - stop_distance_pct)
    now = datetime(2026, 11, 22, 12, 0, 0, tzinfo=UTC)

    config = GateConfig()
    context = GateContext(
        account_equity=equity,
        peak_equity=equity,
        daily_realized_loss=Decimal("0.00"),
        open_positions={},
        open_position_notionals={},
        orders_today_count=0,
        allowed_instruments={"BTC/USDT"},
        last_price=entry_price,
        last_bar_ts=now - timedelta(minutes=15),
        current_ts=now,
        bar_interval=timedelta(hours=4),
        kill_switch_active=False,
        used_idempotency_keys=set(),
        mode="PAPER"
    )

    proposal = OrderProposal(
        proposal_id=uuid.uuid4(),
        idempotency_key=uuid.uuid4(),
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        price=entry_price,
        size=raw_size,
        stop_loss=stop_loss,
        take_profit=entry_price * Decimal("1.05"),
        rationale_id="HYPOTHESIS_TEST"
    )

    gate = RiskGate(config=config)
    decision = gate.evaluate(proposal=proposal, context=context)

    if decision.passed:
        # Invariant 1: Risk amount strictly <= 1% equity
        risk_amount = (entry_price - stop_loss) * raw_size
        max_allowed_risk = equity * config.max_risk_pct
        assert risk_amount <= max_allowed_risk, f"Invariant breached: risk {risk_amount} > {max_allowed_risk}"

        # Invariant 2: Total position notional strictly <= 10% equity
        notional = entry_price * raw_size
        max_allowed_notional = equity * config.max_position_pct
        assert notional <= max_allowed_notional, f"Invariant breached: notional {notional} > {max_allowed_notional}"
