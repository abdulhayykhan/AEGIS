from decimal import Decimal
from enum import Enum
from typing import Any


class TimeframeTrend(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


def check_multitimeframe_alignment(
    tf_1d_trend: TimeframeTrend,
    tf_4h_trend: TimeframeTrend
) -> dict[str, Any]:
    """Verify trend alignment across macro (1D) and execution (4H) timeframes.
    
    Citations:
    - daviddme/TradingView-Unified-MCP: multi-timeframe indicators and timeframe alignment algorithms.
    - daviddme/tradingview-indicator-search-mcp-server: indicator discovery and PineScript technical summaries.
    """
    if tf_1d_trend == TimeframeTrend.BULLISH and tf_4h_trend == TimeframeTrend.BULLISH:
        return {
            "aligned": True,
            "direction": "BUY",
            "confidence": Decimal("1.00"),
            "reason": "1D and 4H timeframes both exhibit bullish trend alignment."
        }
    elif tf_1d_trend == TimeframeTrend.BEARISH and tf_4h_trend == TimeframeTrend.BEARISH:
        return {
            "aligned": True,
            "direction": "SELL",
            "confidence": Decimal("1.00"),
            "reason": "1D and 4H timeframes both exhibit bearish trend alignment."
        }
    else:
        return {
            "aligned": False,
            "direction": "NEUTRAL",
            "confidence": Decimal("0.00"),
            "reason": f"Timeframe conflict: 1D={tf_1d_trend.value} vs 4H={tf_4h_trend.value}."
        }
