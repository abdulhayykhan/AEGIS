from decimal import Decimal

from src.signals.indicators import calculate_atr, calculate_sma, compute_trend_signal
from src.signals.models import Bar, SignalType


def test_sma_hand_calculated():
    """Verify SMA calculation against hand-checked mathematical expectation."""
    # Series of 5 prices: [10, 12, 14, 16, 18] -> Sum = 70 -> SMA = 14.0
    prices = [Decimal(p) for p in ["10.0", "12.0", "14.0", "16.0", "18.0"]]
    sma = calculate_sma(prices, period=5)
    assert sma == Decimal("14.0")


def test_sma_insufficient_data():
    """Verify SMA returns None if there are fewer prices than the period."""
    prices = [Decimal("10.0"), Decimal("12.0")]
    assert calculate_sma(prices, period=5) is None


def test_atr_hand_calculated():
    """Verify ATR calculation with hand-checked True Range values.
    
    Bar 0: High=110, Low=90,  Close=105, PrevClose=None -> TR = 110 - 90 = 20
    Bar 1: High=115, Low=100, Close=112, PrevClose=105  -> TR = max(15, 10, 5) = 15
    Bar 2: High=120, Low=108, Close=118, PrevClose=112  -> TR = max(12, 8, 4) = 12
    Bar 3: High=116, Low=102, Close=104, PrevClose=118  -> TR = max(14, 2, 16) = 16
    
    ATR(period=3) over bars 1..3: (15 + 12 + 16) / 3 = 43 / 3 = 14.3333333333...
    """
    bars = [
        Bar(ts=1000, open=Decimal(100), high=Decimal(110), low=Decimal(90), close=Decimal(105), volume=Decimal(1000)),
        Bar(ts=2000, open=Decimal(106), high=Decimal(115), low=Decimal(100), close=Decimal(112), volume=Decimal(1200)),
        Bar(ts=3000, open=Decimal(113), high=Decimal(120), low=Decimal(108), close=Decimal(118), volume=Decimal(1100)),
        Bar(ts=4000, open=Decimal(117), high=Decimal(116), low=Decimal(102), close=Decimal(104), volume=Decimal(1500)),
    ]
    atr = calculate_atr(bars, period=3)
    assert atr is not None
    # 43 / 3 rounded to 4 decimals = 14.3333
    assert round(atr, 4) == Decimal("14.3333")


def test_signal_golden_regime_and_trend():
    """Verify BUY signal when Close > SMA50 and SMA50 > SMA200 with no position."""
    close = Decimal("150.0")
    sma_50 = Decimal("140.0")
    sma_200 = Decimal("120.0")
    has_position = False

    signal = compute_trend_signal(
        current_close=close,
        sma_50=sma_50,
        sma_200=sma_200,
        has_position=has_position
    )
    assert signal == SignalType.BUY


def test_signal_death_cross_exit():
    """Verify SELL / Exit signal when in position and SMA50 crosses below SMA200."""
    close = Decimal("110.0")
    sma_50 = Decimal("115.0")
    sma_200 = Decimal("120.0")  # SMA50 < SMA200 (Death Cross)
    has_position = True

    signal = compute_trend_signal(
        current_close=close,
        sma_50=sma_50,
        sma_200=sma_200,
        has_position=has_position
    )
    assert signal == SignalType.SELL


def test_signal_abstention_when_not_in_regime():
    """Verify abstention (NEUTRAL / NO_TRADE) when conditions are not met."""
    # Close is below SMA50 even though SMA50 > SMA200
    close = Decimal("135.0")
    sma_50 = Decimal("140.0")
    sma_200 = Decimal("120.0")
    has_position = False

    signal = compute_trend_signal(
        current_close=close,
        sma_50=sma_50,
        sma_200=sma_200,
        has_position=has_position
    )
    assert signal == SignalType.NEUTRAL
