from decimal import Decimal

from src.agent.council import (
    BullBearDebate,
    TradeCouncil,
    TradeMemo,
)
from src.signals.models import Bar
from src.signals.onchain import SmartMoneyMetrics
from src.signals.regime import MarketRegime


def test_agent_council_generates_evidenced_trade_memo() -> None:
    # 30 bars in clear uptrend
    bars = [
        Bar(
            ts=1000 + i * 86400,
            open=Decimal(str(30000 + i * 50)),
            high=Decimal(str(30000 + i * 50 + 100)),
            low=Decimal(str(30000 + i * 50 - 50)),
            close=Decimal(str(30000 + i * 50 + 40)),
            volume=Decimal("15000.0")
        )
        for i in range(30)
    ]
    onchain = SmartMoneyMetrics(
        symbol="BTC/USDT",
        exchange_netflow_usd=Decimal("-40000000.00"),
        whale_accumulation_score=Decimal("80.0"),
        dex_liquidity_change_pct=Decimal("5.0")
    )

    council = TradeCouncil()
    memo = council.deliberate(symbol="BTC/USDT", bars=bars, onchain=onchain, has_position=False)

    assert isinstance(memo, TradeMemo)
    assert memo.symbol == "BTC/USDT"
    assert memo.recommendation == "BUY"
    assert memo.conviction_score >= Decimal("0.70")
    assert "bull_thesis" in memo.model_dump()
    assert "bear_critique" in memo.model_dump()
    assert memo.regime == MarketRegime.TRENDING_BULL
    assert len(memo.citations) >= 2


def test_bull_bear_debate_abstains_on_severe_bear_critique() -> None:
    debate = BullBearDebate()
    result = debate.debate(
        technical_verdict="BUY",
        onchain_verdict="DISTRIBUTION_BEARISH",
        regime=MarketRegime.RANGING
    )
    assert result["recommendation"] == "HOLD"
    assert result["conviction"] < Decimal("0.50")
    assert "Bear warning" in result["synthesis"]
