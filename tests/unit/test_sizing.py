from decimal import Decimal

import pytest

from src.signals.sizing import calculate_position_size


def test_position_sizing_capped_by_instrument_limit():
    """Verify position sizing when capped by the 10% instrument equity limit.
    
    Account equity = 10,000 USDT
    Entry = 100 USDT, Stop = 95 USDT (Risk = 5 USDT/unit)
    1% Risk Budget = 100 USDT -> Raw units = 100 / 5 = 20 units ($2,000 notional = 20% equity)
    10% Equity Cap = 1,000 USDT -> Cap units = 1,000 / 100 = 10 units
    Expected final size = 10 units.
    """
    equity = Decimal("10000.00")
    entry_price = Decimal("100.00")
    stop_loss = Decimal("95.00")
    min_size = Decimal("1.0")
    step_size = Decimal("1.0")

    result = calculate_position_size(
        equity=equity,
        entry_price=entry_price,
        stop_loss=stop_loss,
        min_size=min_size,
        step_size=step_size
    )

    assert result.units == Decimal("10.0")
    assert result.notional_value == Decimal("1000.00")
    assert result.risk_amount == Decimal("50.00")  # 10 units * $5 risk/unit = $50 (0.5% equity)


def test_position_sizing_governed_by_risk_limit():
    """Verify position sizing when stop distance governs the size (under 10% equity cap).
    
    Account equity = 10,000 USDT
    Entry = 100 USDT, Stop = 80 USDT (Risk = 20 USDT/unit)
    1% Risk Budget = 100 USDT -> Raw units = 100 / 20 = 5 units ($500 notional = 5% equity)
    10% Equity Cap = 1,000 USDT -> Cap units = 10 units
    Expected final size = 5 units.
    """
    equity = Decimal("10000.00")
    entry_price = Decimal("100.00")
    stop_loss = Decimal("80.00")
    min_size = Decimal("1.0")
    step_size = Decimal("1.0")

    result = calculate_position_size(
        equity=equity,
        entry_price=entry_price,
        stop_loss=stop_loss,
        min_size=min_size,
        step_size=step_size
    )

    assert result.units == Decimal("5.0")
    assert result.notional_value == Decimal("500.00")
    assert result.risk_amount == Decimal("100.00")  # exactly 1.0% equity


def test_position_sizing_respects_step_size():
    """Verify size is rounded down to step_size precision."""
    equity = Decimal("10000.00")
    entry_price = Decimal("30000.00")  # e.g., BTC
    stop_loss = Decimal("29500.00")     # Stop distance = 500
    # 1% risk budget = 100 USDT -> Raw units = 100 / 500 = 0.2 BTC
    # 10% cap = 1,000 USDT -> Cap units = 1,000 / 30,000 = 0.033333... BTC
    # Final units cap = 0.033333...
    # Step size = 0.001 -> Expect 0.033 BTC
    min_size = Decimal("0.001")
    step_size = Decimal("0.001")

    result = calculate_position_size(
        equity=equity,
        entry_price=entry_price,
        stop_loss=stop_loss,
        min_size=min_size,
        step_size=step_size
    )

    assert result.units == Decimal("0.033")
    assert result.notional_value == Decimal("990.00")


def test_position_sizing_invalid_stop_loss():
    """Verify ValueError is raised if stop_loss >= entry_price for long order."""
    equity = Decimal("10000.00")
    entry_price = Decimal("100.00")
    stop_loss = Decimal("105.00")

    with pytest.raises(ValueError, match="Stop loss must be strictly below entry price"):
        calculate_position_size(
            equity=equity,
            entry_price=entry_price,
            stop_loss=stop_loss,
            min_size=Decimal(1),
            step_size=Decimal(1)
        )
