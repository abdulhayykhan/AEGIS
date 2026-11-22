from decimal import Decimal

from src.signals.sizing import (
    apply_correlation_penalty,
    calculate_volatility_targeted_size,
    check_spread_and_slippage_guard,
)


def test_volatility_targeted_sizing_low_vs_high_vol() -> None:
    equity = Decimal("10000.00")
    price = Decimal("30000.00")

    # Low volatility: ATR = $2000
    res_low = calculate_volatility_targeted_size(
        equity=equity,
        entry_price=price,
        current_atr=Decimal("2000.00"),
        target_vol_pct=Decimal("0.15"),
        max_position_pct=Decimal("0.50")
    )

    # High volatility: ATR = $6000
    res_high = calculate_volatility_targeted_size(
        equity=equity,
        entry_price=price,
        current_atr=Decimal("6000.00"),
        target_vol_pct=Decimal("0.15"),
        max_position_pct=Decimal("0.50")
    )

    # Higher volatility must result in smaller position size
    assert res_high.units < res_low.units
    assert res_low.units > Decimal(0)
    assert res_high.units > Decimal(0)


def test_correlation_penalty_reduces_size() -> None:
    raw_size = Decimal("0.05")
    # No correlated positions: 0% reduction
    penalized_zero = apply_correlation_penalty(
        raw_size=raw_size,
        symbol="BTC/USDT",
        open_positions=["SOL/USDT"],
        correlation_matrix={"BTC/USDT": {"SOL/USDT": Decimal("0.30")}}
    )
    assert penalized_zero == raw_size

    # Highly correlated position (ETH/USDT correlation 0.85): penalty applied
    penalized_high = apply_correlation_penalty(
        raw_size=raw_size,
        symbol="BTC/USDT",
        open_positions=["ETH/USDT"],
        correlation_matrix={"BTC/USDT": {"ETH/USDT": Decimal("0.85")}}
    )
    assert penalized_high < raw_size


def test_spread_and_slippage_guard() -> None:
    mark = Decimal("30000.00")
    # Acceptable spread (0.2%)
    ok, _msg = check_spread_and_slippage_guard(
        limit_price=Decimal("30060.00"),
        mark_price=mark,
        max_allowed_spread_pct=Decimal("0.01")
    )
    assert ok is True

    # Extreme spread / slippage (> 2%)
    ok_breach, msg_breach = check_spread_and_slippage_guard(
        limit_price=Decimal("30800.00"),
        mark_price=mark,
        max_allowed_spread_pct=Decimal("0.01")
    )
    assert ok_breach is False
    assert "exceeds maximum allowed" in msg_breach
