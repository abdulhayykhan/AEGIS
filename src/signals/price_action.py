import math
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict

from src.signals.indicators import calculate_sma
from src.signals.models import Bar


class FVGType(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"


class FairValueGap(BaseModel):
    model_config = ConfigDict(frozen=True)

    fvg_type: FVGType
    top: Decimal
    bottom: Decimal
    gap_size: Decimal
    bar_index: int


class BollingerBands(BaseModel):
    model_config = ConfigDict(frozen=True)

    upper: Decimal
    middle: Decimal
    lower: Decimal
    bandwidth: Decimal
    pct_b: Decimal


def calculate_rsi(prices: list[Decimal], period: int = 14) -> Decimal | None:
    """Calculate Relative Strength Index (RSI) using Wilder's smoothing.
    
    Citations:
    - tradermonty/claude-trading-skills: momentum & oscillator specifications.
    - agiprolabs/claude-trading-skills: quantitative indicator implementations.
    """
    if len(prices) <= period or period <= 0:
        return None

    gains: list[Decimal] = []
    losses: list[Decimal] = []

    for i in range(1, len(prices)):
        diff = prices[i] - prices[i - 1]
        if diff > Decimal(0):
            gains.append(diff)
            losses.append(Decimal(0))
        else:
            gains.append(Decimal(0))
            losses.append(abs(diff))

    if len(gains) < period:
        return None

    # Initial average
    avg_gain = sum(gains[:period]) / Decimal(period)
    avg_loss = sum(losses[:period]) / Decimal(period)

    # Wilder's smoothing
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * Decimal(period - 1) + gains[i]) / Decimal(period)
        avg_loss = (avg_loss * Decimal(period - 1) + losses[i]) / Decimal(period)

    if avg_loss == Decimal(0):
        return Decimal("100.00") if avg_gain > Decimal(0) else Decimal("50.00")
    if avg_gain == Decimal(0):
        return Decimal("0.00")

    rs = avg_gain / avg_loss
    rsi = Decimal("100.00") - (Decimal("100.00") / (Decimal("1.00") + rs))
    return round(rsi, 2)


def calculate_bollinger_bands(
    prices: list[Decimal],
    period: int = 20,
    std_dev_multiplier: Decimal = Decimal("2.0")
) -> BollingerBands | None:
    """Calculate Bollinger Bands (Upper, Middle, Lower, Bandwidth, %B).
    
    Citations:
    - daviddme/TradingView-Unified-MCP: technical indicator schema & outputs.
    - marian2js/trading-skills: volatility bands calculation.
    """
    if len(prices) < period or period <= 0:
        return None

    middle = calculate_sma(prices, period)
    if middle is None:
        return None

    window = prices[-period:]
    variance = sum((p - middle) ** 2 for p in window) / Decimal(period)
    std_dev = Decimal(str(math.sqrt(float(variance))))

    upper = middle + (std_dev * std_dev_multiplier)
    lower = middle - (std_dev * std_dev_multiplier)

    bandwidth = ((upper - lower) / middle * Decimal("100.00")) if middle > Decimal(0) else Decimal("0.00")
    current_price = prices[-1]
    denom = upper - lower
    pct_b = ((current_price - lower) / denom) if denom > Decimal(0) else Decimal("0.50")

    return BollingerBands(
        upper=round(upper, 2),
        middle=round(middle, 2),
        lower=round(lower, 2),
        bandwidth=round(bandwidth, 2),
        pct_b=round(pct_b, 4)
    )


def detect_fair_value_gaps(bars: list[Bar], min_gap_usd: Decimal = Decimal("0.01")) -> list[FairValueGap]:
    """Detect Fair Value Gaps (FVG) across consecutive 3-bar price structures.
    
    Citations:
    - tradermonty/claude-trading-skills: ICT Fair Value Gap, liquidity void, and order block identification.
    """
    if len(bars) < 3:
        return []

    fvgs: list[FairValueGap] = []
    for i in range(2, len(bars)):
        bar_prior = bars[i - 2]
        bar_current = bars[i]

        # Bullish FVG: Current bar's Low > Prior bar's High (Bar i-1 was an expansive up candle)
        if bar_current.low > bar_prior.high:
            gap = bar_current.low - bar_prior.high
            if gap >= min_gap_usd:
                fvgs.append(
                    FairValueGap(
                        fvg_type=FVGType.BULLISH,
                        top=round(bar_current.low, 2),
                        bottom=round(bar_prior.high, 2),
                        gap_size=round(gap, 2),
                        bar_index=i
                    )
                )

        # Bearish FVG: Current bar's High < Prior bar's Low (Bar i-1 was an expansive down candle)
        elif bar_current.high < bar_prior.low:
            gap = bar_prior.low - bar_current.high
            if gap >= min_gap_usd:
                fvgs.append(
                    FairValueGap(
                        fvg_type=FVGType.BEARISH,
                        top=round(bar_prior.low, 2),
                        bottom=round(bar_current.high, 2),
                        gap_size=round(gap, 2),
                        bar_index=i
                    )
                )

    return fvgs
