from decimal import Decimal

from src.signals.multitimeframe import (
    TimeframeTrend,
    check_multitimeframe_alignment,
)
from src.signals.onchain import (
    OnChainBias,
    SmartMoneyMetrics,
    compute_smart_money_bias,
)


def test_onchain_smart_money_bias() -> None:
    # 1. Bullish smart money accumulation
    bull_metrics = SmartMoneyMetrics(
        symbol="BTC/USDT",
        exchange_netflow_usd=Decimal("-50000000.00"),  # Outflows from exchange (holding)
        whale_accumulation_score=Decimal("85.0"),
        dex_liquidity_change_pct=Decimal("4.5")
    )
    bias_bull = compute_smart_money_bias(bull_metrics)
    assert bias_bull == OnChainBias.ACCUMULATION_BULLISH

    # 2. Bearish smart money distribution
    bear_metrics = SmartMoneyMetrics(
        symbol="BTC/USDT",
        exchange_netflow_usd=Decimal("75000000.00"),  # Inflows to exchange (selling)
        whale_accumulation_score=Decimal("20.0"),
        dex_liquidity_change_pct=Decimal("-8.2")
    )
    bias_bear = compute_smart_money_bias(bear_metrics)
    assert bias_bear == OnChainBias.DISTRIBUTION_BEARISH


def test_multitimeframe_trend_alignment() -> None:
    # 1. Aligned Bullish (1D Bullish, 4H Bullish)
    align_bull = check_multitimeframe_alignment(
        tf_1d_trend=TimeframeTrend.BULLISH,
        tf_4h_trend=TimeframeTrend.BULLISH
    )
    assert align_bull["aligned"] is True
    assert align_bull["direction"] == "BUY"

    # 2. Conflicted (1D Bullish, 4H Bearish)
    conflicted = check_multitimeframe_alignment(
        tf_1d_trend=TimeframeTrend.BULLISH,
        tf_4h_trend=TimeframeTrend.BEARISH
    )
    assert conflicted["aligned"] is False
    assert conflicted["direction"] == "NEUTRAL"
