from datetime import UTC, datetime, timedelta
from decimal import Decimal

from src.signals.indicators import calculate_atr, calculate_sma, compute_trend_signal
from src.signals.models import Bar
from src.signals.sizing import calculate_position_size


def test_deterministic_replay_stored_day():
    """Verify that replaying a stored day produces identical, deterministic output."""
    # Fixed historical sequence of six 4-hour bars (one complete 24-hour day)
    base_time = datetime(2026, 1, 15, 0, 0, 0, tzinfo=UTC)
    historical_bars = [
        Bar(ts=int((base_time + timedelta(hours=4 * i)).timestamp()),
            open=Decimal(str(100 + i * 2)),
            high=Decimal(str(105 + i * 2)),
            low=Decimal(str(98 + i * 2)),
            close=Decimal(str(103 + i * 2)),
            volume=Decimal("15000.0"))
        for i in range(6)
    ]

    def run_pipeline(bars):
        closes = [b.close for b in bars]
        sma_3 = calculate_sma(closes, period=3)
        atr_3 = calculate_atr(bars, period=3)
        assert atr_3 is not None
        signal = compute_trend_signal(
            current_close=closes[-1],
            sma_50=Decimal("100.0"),  # Baseline reference
            sma_200=Decimal("95.0"),
            has_position=False
        )
        sizing = calculate_position_size(
            equity=Decimal("10000.0"),
            entry_price=closes[-1],
            stop_loss=closes[-1] - (Decimal("2.0") * atr_3),
            min_size=Decimal("0.1"),
            step_size=Decimal("0.1")
        )
        return {
            "sma_3": sma_3,
            "atr_3": atr_3,
            "signal": signal,
            "units": sizing.units,
            "notional": sizing.notional_value,
            "risk": sizing.risk_amount
        }

    # Execute pass 1
    run1 = run_pipeline(historical_bars)
    # Execute pass 2 (independent replay)
    run2 = run_pipeline(historical_bars)

    # Both runs must be strictly, deterministically identical
    assert run1 == run2
    assert run1["signal"].value == "BUY"
    assert run1["units"] > Decimal(0)
