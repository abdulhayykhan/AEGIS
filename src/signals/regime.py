from decimal import Decimal
from enum import Enum

from src.signals.indicators import calculate_sma


class MarketRegime(str, Enum):
    TRENDING_BULL = "TRENDING_BULL"
    TRENDING_BEAR = "TRENDING_BEAR"
    RANGING = "RANGING"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"


def classify_market_regime(
    closes: list[Decimal],
    period_short: int = 10,
    period_long: int = 30,
    trend_threshold_pct: Decimal = Decimal("1.0")
) -> MarketRegime:
    """Classify market regime into trending, ranging, or volatile states.
    
    Citations:
    - agiprolabs/claude-trading-skills: market regime classification & adaptive strategy switching.
    - TauricResearch/TradingAgents: macro market context conditioning for trading agents.
    """
    if len(closes) < period_long or period_long <= period_short:
        return MarketRegime.RANGING

    sma_short = calculate_sma(closes, period_short)
    sma_long = calculate_sma(closes, period_long)

    if sma_short is None or sma_long is None or sma_long == Decimal(0):
        return MarketRegime.RANGING

    diff_pct = (sma_short - sma_long) / sma_long * Decimal("100.00")

    if diff_pct > trend_threshold_pct and closes[-1] >= sma_short:
        return MarketRegime.TRENDING_BULL
    elif diff_pct < -trend_threshold_pct and closes[-1] <= sma_short:
        return MarketRegime.TRENDING_BEAR
    else:
        return MarketRegime.RANGING
