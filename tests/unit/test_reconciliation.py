from decimal import Decimal

from src.gate.reconcile import AccountState, PositionState, reconcile_states


def test_reconciliation_exact_match() -> None:
    """Verify reconciliation reports match=True when DB and Broker match to the cent."""
    db_state = AccountState(
        equity=Decimal("10000.00"),
        cash=Decimal("9010.00"),
        positions={"BTC/USDT": PositionState(symbol="BTC/USDT", size=Decimal("0.033"), avg_price=Decimal("30000.00"))}
    )
    broker_state = AccountState(
        equity=Decimal("10000.00"),
        cash=Decimal("9010.00"),
        positions={"BTC/USDT": PositionState(symbol="BTC/USDT", size=Decimal("0.033"), avg_price=Decimal("30000.00"))}
    )

    result = reconcile_states(db_state=db_state, broker_state=broker_state)
    assert result.match is True
    assert len(result.diffs) == 0


def test_reconciliation_cash_mismatch() -> None:
    """Verify reconciliation detects discrepancy in cash balances."""
    db_state = AccountState(
        equity=Decimal("10000.00"),
        cash=Decimal("9010.00"),
        positions={}
    )
    broker_state = AccountState(
        equity=Decimal("9950.00"),
        cash=Decimal("8960.00"),  # $50 discrepancy
        positions={}
    )

    result = reconcile_states(db_state=db_state, broker_state=broker_state)
    assert result.match is False
    assert any("Cash mismatch" in d for d in result.diffs)


def test_reconciliation_position_mismatch() -> None:
    """Verify reconciliation detects missing or divergent position size."""
    db_state = AccountState(
        equity=Decimal("10000.00"),
        cash=Decimal("10000.00"),
        positions={"ETH/USDT": PositionState(symbol="ETH/USDT", size=Decimal("1.0"), avg_price=Decimal("2000.00"))}
    )
    broker_state = AccountState(
        equity=Decimal("10000.00"),
        cash=Decimal("10000.00"),
        positions={}  # Broker has no position
    )

    result = reconcile_states(db_state=db_state, broker_state=broker_state)
    assert result.match is False
    assert any("Missing position" in d or "Size mismatch" in d for d in result.diffs)
