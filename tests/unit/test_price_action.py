from decimal import Decimal

from src.signals.models import Bar
from src.signals.price_action import (
    BollingerBands,
    FVGType,
    calculate_bollinger_bands,
    calculate_rsi,
    detect_fair_value_gaps,
)
from src.signals.regime import MarketRegime, classify_market_regime


def test_calculate_rsi_bounds_and_values() -> None:
    # Monotonically increasing prices -> RSI = 100
    up_prices = [Decimal(str(100 + i * 5)) for i in range(20)]
    rsi_up = calculate_rsi(up_prices, period=14)
    assert rsi_up is not None
    assert rsi_up == Decimal("100.00")

    # Monotonically decreasing prices -> RSI = 0
    down_prices = [Decimal(str(200 - i * 5)) for i in range(20)]
    rsi_down = calculate_rsi(down_prices, period=14)
    assert rsi_down is not None
    assert rsi_down == Decimal("0.00")

    # Too few prices -> None
    assert calculate_rsi([Decimal(100)], period=14) is None


def test_calculate_bollinger_bands() -> None:
    prices = [Decimal(str(100 + (i % 5))) for i in range(25)]
    bb = calculate_bollinger_bands(prices, period=20, std_dev_multiplier=Decimal("2.0"))
    assert bb is not None
    assert isinstance(bb, BollingerBands)
    assert bb.upper >= bb.middle >= bb.lower
    assert bb.bandwidth > Decimal("0.00")


def test_detect_fair_value_gaps() -> None:
    # Construct 3 bars with a Bullish FVG (Bar 0 High < Bar 2 Low)
    bars = [
        Bar(ts=1000, open=Decimal(100), high=Decimal(102), low=Decimal(99), close=Decimal(101), volume=Decimal(1000)),
        Bar(ts=2000, open=Decimal(101), high=Decimal(110), low=Decimal(101), close=Decimal(109), volume=Decimal(5000)),
        Bar(ts=3000, open=Decimal(109), high=Decimal(112), low=Decimal(105), close=Decimal(111), volume=Decimal(2000)),
    ]
    fvgs = detect_fair_value_gaps(bars)
    assert len(fvgs) == 1
    fvg = fvgs[0]
    assert fvg.fvg_type == FVGType.BULLISH
    assert fvg.top == Decimal(105)  # Bar 2 low
    assert fvg.bottom == Decimal(102)  # Bar 0 high
    assert fvg.gap_size == Decimal("3.00")


def test_classify_market_regime() -> None:
    # Strongly trending upward series
    closes_bull = [Decimal(str(100 + i * 2)) for i in range(50)]
    regime_bull = classify_market_regime(closes_bull, period_short=10, period_long=30)
    assert regime_bull == MarketRegime.TRENDING_BULL

    # Strongly trending downward series
    closes_bear = [Decimal(str(200 - i * 2)) for i in range(50)]
    regime_bear = classify_market_regime(closes_bear, period_short=10, period_long=30)
    assert regime_bear == MarketRegime.TRENDING_BEAR

    # Flat sideways series
    closes_range = [Decimal("100.00") if i % 2 == 0 else Decimal("100.50") for i in range(50)]
    regime_range = classify_market_regime(closes_range, period_short=10, period_long=30)
    assert regime_range == MarketRegime.RANGING
