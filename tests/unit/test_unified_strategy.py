from decimal import Decimal

from src.signals.models import Bar, SignalType
from src.signals.strategy import StrategyConfig, evaluate_strategy


def create_bars(prices: list[float]) -> list[Bar]:
    return [
        Bar(
            ts=1700000000 + (i * 86400),
            open=Decimal(str(p)),
            high=Decimal(str(p + 100)),
            low=Decimal(str(p - 100)),
            close=Decimal(str(p)),
            volume=Decimal("1000.0")
        )
        for i, p in enumerate(prices)
    ]


def test_unified_strategy_insufficient_bars() -> None:
    bars = create_bars([30000.0 + i for i in range(10)])
    config = StrategyConfig(fast_period=50, slow_period=200, atr_period=14, min_warmup_bars=20)
    sig = evaluate_strategy(bars=bars, has_position=False, config=config)
    assert sig.signal == SignalType.NEUTRAL
    assert sig.regime is not None


def test_unified_strategy_bullish_entry_signal() -> None:
    # Generate 60 bars in steady uptrend
    prices = [20000.0 + (i * 200.0) for i in range(60)]
    bars = create_bars(prices)
    config = StrategyConfig(fast_period=15, slow_period=40, atr_period=10, min_warmup_bars=45)
    sig = evaluate_strategy(bars=bars, has_position=False, config=config)
    assert sig.signal == SignalType.BUY
    assert sig.sma_fast is not None
    assert sig.sma_slow is not None
    assert sig.sma_fast > sig.sma_slow
    assert sig.atr is not None and sig.atr > Decimal(0)
    assert sig.conviction > Decimal("0.50")


def test_unified_strategy_bearish_exit_signal() -> None:
    # Uptrend then sharp decline
    prices = [25000.0 + (i * 100.0) for i in range(50)] + [30000.0 - (i * 500.0) for i in range(15)]
    bars = create_bars(prices)
    config = StrategyConfig(fast_period=15, slow_period=40, atr_period=10, min_warmup_bars=45)
    sig = evaluate_strategy(bars=bars, has_position=True, config=config)
    assert sig.signal == SignalType.SELL
