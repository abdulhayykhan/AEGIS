from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict


class OnChainBias(str, Enum):
    ACCUMULATION_BULLISH = "ACCUMULATION_BULLISH"
    DISTRIBUTION_BEARISH = "DISTRIBUTION_BEARISH"
    NEUTRAL = "NEUTRAL"


class SmartMoneyMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    exchange_netflow_usd: Decimal
    whale_accumulation_score: Decimal  # 0 to 100
    dex_liquidity_change_pct: Decimal


def compute_smart_money_bias(metrics: SmartMoneyMetrics) -> OnChainBias:
    """Analyze smart money token netflows and whale wallet accumulation.
    
    Citations:
    - nansen-ai/nansen-cli: On-chain smart money tracking, wallet profiling, exchange netflows, and DEX liquidity analytics.
    """
    if metrics.exchange_netflow_usd < Decimal(0) and metrics.whale_accumulation_score >= Decimal("60.0"):
        return OnChainBias.ACCUMULATION_BULLISH
    elif metrics.exchange_netflow_usd > Decimal(0) and metrics.whale_accumulation_score <= Decimal("40.0"):
        return OnChainBias.DISTRIBUTION_BEARISH
    else:
        return OnChainBias.NEUTRAL
