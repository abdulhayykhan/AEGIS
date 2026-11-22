from decimal import Decimal

from src.signals.models import Bar, SignalType


def calculate_sma(prices: list[Decimal], period: int) -> Decimal | None:
    """Calculate Simple Moving Average (SMA) over the given period.
    
    Returns None if fewer than `period` prices are provided.
    """
    if len(prices) < period or period <= 0:
        return None
    window = prices[-period:]
    return sum(window) / Decimal(period)


def calculate_atr(bars: list[Bar], period: int) -> Decimal | None:
    """Calculate Average True Range (ATR) over the given period using Simple Moving Average of TR.
    
    TR(0) = High - Low
    TR(t) = max(High(t) - Low(t), |High(t) - Close(t-1)|, |Low(t) - Close(t-1)|)
    
    Returns None if fewer than `period` bars are provided.
    """
    if len(bars) < period or period <= 0:
        return None

    tr_list: list[Decimal] = []
    for i, bar in enumerate(bars):
        if i == 0:
            tr = bar.high - bar.low
        else:
            prev_close = bars[i - 1].close
            tr1 = bar.high - bar.low
            tr2 = abs(bar.high - prev_close)
            tr3 = abs(bar.low - prev_close)
            tr = max(tr1, tr2, tr3)
        tr_list.append(tr)

    # Average the last `period` TR values
    recent_tr = tr_list[-period:]
    return sum(recent_tr) / Decimal(period)


def compute_trend_signal(
    current_close: Decimal,
    sma_50: Decimal | None,
    sma_200: Decimal | None,
    has_position: bool
) -> SignalType:
    """Compute trend-following signal according to docs/strategy-spec.md.
    
    Rules:
    - Long Entry (BUY): Close > SMA50 AND SMA50 > SMA200 AND NOT has_position
    - Long Exit (SELL): has_position AND (Close < SMA50 OR SMA50 < SMA200)
    - Abstain (NEUTRAL): All other cases
    """
    if sma_50 is None or sma_200 is None:
        return SignalType.NEUTRAL

    if not has_position:
        if current_close > sma_50 > sma_200:
            return SignalType.BUY
    else:
        if current_close < sma_50 or sma_50 < sma_200:
            return SignalType.SELL

    return SignalType.NEUTRAL
