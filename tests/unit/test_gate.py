import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from src.gate.evaluator import GateConfig, RiskGate
from src.gate.models import GateContext, OrderProposal, OrderSide, OrderType


@pytest.fixture
def base_config() -> GateConfig:
    return GateConfig(
        max_risk_pct=Decimal("0.01"),       # 1%
        max_position_pct=Decimal("0.10"),   # 10%
        max_exposure_pct=Decimal("0.50"),   # 50%
        max_open_positions=3,
        max_orders_per_day=6,
        max_daily_loss_pct=Decimal("0.02"), # 2%
        max_drawdown_pct=Decimal("0.08"),   # 8%
        price_sanity_pct=Decimal("0.02"),   # 2%
    )


@pytest.fixture
def base_context() -> GateContext:
    now = datetime(2026, 11, 22, 12, 0, 0, tzinfo=UTC)
    return GateContext(
        account_equity=Decimal("10000.00"),
        peak_equity=Decimal("10000.00"),
        daily_realized_loss=Decimal("0.00"),
        open_positions={"BTC/USDT": Decimal("0.0")},
        open_position_notionals={"BTC/USDT": Decimal("0.0")},
        orders_today_count=0,
        allowed_instruments={"BTC/USDT", "ETH/USDT", "SOL/USDT"},
        last_price=Decimal("30000.00"),
        last_bar_ts=now - timedelta(minutes=30),
        current_ts=now,
        bar_interval=timedelta(hours=4),
        kill_switch_active=False,
        used_idempotency_keys=set(),
        mode="PAPER"
    )


@pytest.fixture
def valid_proposal() -> OrderProposal:
    # Equity = 10,000, 1% risk budget = 100
    # Entry = 30,000, Stop = 29,000 (Distance = 1,000)
    # Size = 0.033 BTC -> Risk = 33 USDT (0.33% <= 1%)
    # Notional = 0.033 * 30,000 = 990 USDT (9.9% <= 10%)
    return OrderProposal(
        proposal_id=uuid.uuid4(),
        idempotency_key=uuid.uuid4(),
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        price=Decimal("30000.00"),
        size=Decimal("0.033"),
        stop_loss=Decimal("29000.00"),
        take_profit=Decimal("32000.00"),
        rationale_id="SMA_CROSS_001"
    )


def test_gate_accepts_valid_proposal(base_config: GateConfig, base_context: GateContext, valid_proposal: OrderProposal) -> None:
    """Check that an order strictly within all limits passes cleanly."""
    gate = RiskGate(config=base_config)
    decision = gate.evaluate(proposal=valid_proposal, context=base_context)
    assert decision.passed is True
    assert len(decision.reasons) == 0


def test_gate_rejects_kill_switch_active(base_config: GateConfig, base_context: GateContext, valid_proposal: OrderProposal) -> None:
    """Step 1: Reject order immediately if kill switch is engaged."""
    base_context.kill_switch_active = True
    gate = RiskGate(config=base_config)
    decision = gate.evaluate(proposal=valid_proposal, context=base_context)
    assert decision.passed is False
    assert any("kill switch" in r.lower() for r in decision.reasons)


def test_gate_rejects_unapproved_instrument(base_config: GateConfig, base_context: GateContext, valid_proposal: OrderProposal) -> None:
    """Step 2: Reject instrument not in allow list."""
    invalid_proposal = valid_proposal.model_copy(update={"symbol": "DOGE/USDT"})
    gate = RiskGate(config=base_config)
    decision = gate.evaluate(proposal=invalid_proposal, context=base_context)
    assert decision.passed is False
    assert any("not on allow list" in r.lower() for r in decision.reasons)


def test_gate_rejects_market_order(base_config: GateConfig, base_context: GateContext, valid_proposal: OrderProposal) -> None:
    """Step 2: Prohibit market orders except for kill switch."""
    invalid_proposal = valid_proposal.model_copy(update={"order_type": OrderType.MARKET})
    gate = RiskGate(config=base_config)
    decision = gate.evaluate(proposal=invalid_proposal, context=base_context)
    assert decision.passed is False
    assert any("market order" in r.lower() for r in decision.reasons)


def test_gate_rejects_stale_data(base_config: GateConfig, base_context: GateContext, valid_proposal: OrderProposal) -> None:
    """Step 3: Reject order if market bar is older than 2 bar intervals."""
    # Bar timestamp is 9 hours ago on a 4-hour timeframe (> 8h lag)
    base_context.last_bar_ts = base_context.current_ts - timedelta(hours=9)
    gate = RiskGate(config=base_config)
    decision = gate.evaluate(proposal=valid_proposal, context=base_context)
    assert decision.passed is False
    assert any("stale" in r.lower() for r in decision.reasons)


def test_gate_rejects_max_open_positions_exceeded(base_config: GateConfig, base_context: GateContext, valid_proposal: OrderProposal) -> None:
    """Step 4: Reject if adding position exceeds max open positions (3)."""
    base_context.open_positions = {
        "ETH/USDT": Decimal("1.5"),
        "SOL/USDT": Decimal("20.0"),
        "ADA/USDT": Decimal("500.0")
    }
    gate = RiskGate(config=base_config)
    decision = gate.evaluate(proposal=valid_proposal, context=base_context)
    assert decision.passed is False
    assert any("open positions" in r.lower() for r in decision.reasons)


def test_gate_rejects_daily_order_cap(base_config: GateConfig, base_context: GateContext, valid_proposal: OrderProposal) -> None:
    """Step 4: Reject 7th order if max orders today (6) is reached."""
    base_context.orders_today_count = 6
    gate = RiskGate(config=base_config)
    decision = gate.evaluate(proposal=valid_proposal, context=base_context)
    assert decision.passed is False
    assert any("daily order limit" in r.lower() for r in decision.reasons)


def test_gate_rejects_daily_loss_breach(base_config: GateConfig, base_context: GateContext, valid_proposal: OrderProposal) -> None:
    """Step 4: Halt and reject if daily loss reaches 2% of equity ($200)."""
    base_context.daily_realized_loss = Decimal("205.00")
    gate = RiskGate(config=base_config)
    decision = gate.evaluate(proposal=valid_proposal, context=base_context)
    assert decision.passed is False
    assert any("daily loss" in r.lower() for r in decision.reasons)


def test_gate_rejects_peak_drawdown_breach(base_config: GateConfig, base_context: GateContext, valid_proposal: OrderProposal) -> None:
    """Step 4: Freeze and reject if peak drawdown reaches 8%."""
    # Peak = 10,000, Current Equity = 9,150 -> 8.5% drawdown
    base_context.account_equity = Decimal("9150.00")
    base_context.peak_equity = Decimal("10000.00")
    gate = RiskGate(config=base_config)
    decision = gate.evaluate(proposal=valid_proposal, context=base_context)
    assert decision.passed is False
    assert any("drawdown" in r.lower() for r in decision.reasons)


def test_gate_rejects_excessive_instrument_position(base_config: GateConfig, base_context: GateContext, valid_proposal: OrderProposal) -> None:
    """Step 4: Reject if total instrument value exceeds 10% equity ($1,000)."""
    # Size 0.05 BTC * 30,000 = $1,500 (15% of equity)
    invalid_proposal = valid_proposal.model_copy(update={"size": Decimal("0.05")})
    gate = RiskGate(config=base_config)
    decision = gate.evaluate(proposal=invalid_proposal, context=base_context)
    assert decision.passed is False
    assert any("instrument position" in r.lower() for r in decision.reasons)


def test_gate_rejects_excessive_portfolio_exposure(base_config: GateConfig, base_context: GateContext, valid_proposal: OrderProposal) -> None:
    """Step 4: Reject if total portfolio exposure exceeds 50% equity ($5,000)."""
    base_context.open_position_notionals = {
        "ETH/USDT": Decimal("2500.00"),
        "SOL/USDT": Decimal("2000.00")
    }  # Existing exposure = 4,500. New proposal = 990 -> Total = 5,490 (> 5,000)
    gate = RiskGate(config=base_config)
    decision = gate.evaluate(proposal=valid_proposal, context=base_context)
    assert decision.passed is False
    assert any("total exposure" in r.lower() for r in decision.reasons)


def test_gate_rejects_excessive_per_trade_risk(base_config: GateConfig, base_context: GateContext, valid_proposal: OrderProposal) -> None:
    """Step 5: Reject if risk to stop loss exceeds 1% equity ($100)."""
    # Entry = 30,000, Stop = 25,000 (Distance = 5,000). Size = 0.03 -> Risk = 150 (> 100)
    invalid_proposal = valid_proposal.model_copy(
        update={"size": Decimal("0.03"), "stop_loss": Decimal("25000.00")}
    )
    gate = RiskGate(config=base_config)
    decision = gate.evaluate(proposal=invalid_proposal, context=base_context)
    assert decision.passed is False
    assert any("risk per trade" in r.lower() for r in decision.reasons)


def test_gate_rejects_price_out_of_sanity_band(base_config: GateConfig, base_context: GateContext, valid_proposal: OrderProposal) -> None:
    """Step 5: Reject limit price deviating > 2% from last mark price."""
    # Last price = 30,000. Limit price = 30,700 (+2.33% > 2.0%)
    invalid_proposal = valid_proposal.model_copy(update={"price": Decimal("30700.00")})
    gate = RiskGate(config=base_config)
    decision = gate.evaluate(proposal=invalid_proposal, context=base_context)
    assert decision.passed is False
    assert any("price sanity" in r.lower() for r in decision.reasons)


def test_gate_rejects_duplicate_idempotency_key(base_config: GateConfig, base_context: GateContext, valid_proposal: OrderProposal) -> None:
    """Step 6: Reject proposal if idempotency key was previously used."""
    base_context.used_idempotency_keys.add(valid_proposal.idempotency_key)
    gate = RiskGate(config=base_config)
    decision = gate.evaluate(proposal=valid_proposal, context=base_context)
    assert decision.passed is False
    assert any("idempotency key" in r.lower() for r in decision.reasons)

