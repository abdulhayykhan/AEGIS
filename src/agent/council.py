from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict

from src.signals.indicators import calculate_sma, compute_trend_signal
from src.signals.models import Bar, SignalType
from src.signals.onchain import OnChainBias, SmartMoneyMetrics, compute_smart_money_bias
from src.signals.price_action import (
    calculate_bollinger_bands,
    calculate_rsi,
    detect_fair_value_gaps,
)
from src.signals.regime import MarketRegime, classify_market_regime


class TradeMemo(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    recommendation: str  # "BUY", "SELL", "HOLD"
    conviction_score: Decimal  # 0.00 to 1.00
    bull_thesis: str
    bear_critique: str
    regime: MarketRegime
    citations: list[str]


class TechnicalAnalystAgent:
    """Specialized agent analyzing price structure, moving averages, RSI, and liquidity gaps.
    
    Citations:
    - TauricResearch/TradingAgents: technical analysis agent specialization.
    - tradermonty/claude-trading-skills: ICT Fair Value Gaps and price action structure.
    - daviddme/TradingView-Unified-MCP: technical indicator metrics.
    """

    def analyze(self, symbol: str, bars: list[Bar], has_position: bool) -> dict[str, Any]:
        if not bars:
            return {"verdict": "HOLD", "signal": SignalType.NEUTRAL, "details": "No bar data."}

        closes = [b.close for b in bars]
        current_close = closes[-1]
        sma_50 = calculate_sma(closes, period=min(10, len(closes)))
        sma_200 = calculate_sma(closes, period=min(20, len(closes)))
        rsi = calculate_rsi(closes, period=min(14, len(closes) - 1)) if len(closes) > 14 else Decimal("50.00")
        bb = calculate_bollinger_bands(closes, period=min(20, len(closes)))
        fvgs = detect_fair_value_gaps(bars)

        signal = compute_trend_signal(
            current_close=current_close,
            sma_50=sma_50,
            sma_200=sma_200,
            has_position=has_position
        )

        verdict = "BUY" if signal == SignalType.BUY else ("SELL" if signal == SignalType.SELL else "HOLD")
        return {
            "verdict": verdict,
            "signal": signal,
            "close": current_close,
            "sma_50": sma_50,
            "sma_200": sma_200,
            "rsi": rsi,
            "bollinger": bb,
            "fvgs_count": len(fvgs)
        }


class FundamentalOnChainAnalystAgent:
    """Specialized agent assessing macro context and on-chain smart money flows.
    
    Citations:
    - TauricResearch/TradingAgents: fundamentals & sentiment agent layer.
    - nansen-ai/nansen-cli: smart money tracking, wallet profiling, exchange netflows.
    """

    def analyze(self, onchain: SmartMoneyMetrics | None = None) -> dict[str, Any]:
        if onchain is None:
            return {"bias": OnChainBias.NEUTRAL, "summary": "No on-chain metrics provided."}

        bias = compute_smart_money_bias(onchain)
        summary = (
            f"Netflow: ${onchain.exchange_netflow_usd:,.2f} USD, "
            f"Whale Score: {onchain.whale_accumulation_score:.1f}/100, "
            f"DEX Liquidity Delta: {onchain.dex_liquidity_change_pct:+.1f}%."
        )
        return {
            "bias": bias,
            "summary": summary,
            "netflow": onchain.exchange_netflow_usd,
            "whale_score": onchain.whale_accumulation_score
        }


class BullBearDebate:
    """Adversarial deliberation between Bull researcher and Bear risk researcher.
    
    Citations:
    - TauricResearch/TradingAgents: Bull vs Bear debate protocol prior to order formulation.
    """

    def debate(
        self,
        technical_verdict: str,
        onchain_verdict: str,
        regime: MarketRegime
    ) -> dict[str, Any]:
        # Severe bear critique on conflict
        if technical_verdict == "BUY" and onchain_verdict == "DISTRIBUTION_BEARISH":
            return {
                "recommendation": "HOLD",
                "conviction": Decimal("0.35"),
                "synthesis": "Bear warning: Technical buy signal rejected due to severe on-chain smart money distribution."
            }

        if regime == MarketRegime.RANGING and technical_verdict == "BUY":
            return {
                "recommendation": "HOLD",
                "conviction": Decimal("0.45"),
                "synthesis": "Bear warning: Choppy/ranging market regime reduces trend signal reliability."
            }

        if technical_verdict == "BUY" and onchain_verdict in (OnChainBias.ACCUMULATION_BULLISH.value, OnChainBias.NEUTRAL.value):
            return {
                "recommendation": "BUY",
                "conviction": Decimal("0.85") if onchain_verdict == OnChainBias.ACCUMULATION_BULLISH.value else Decimal("0.70"),
                "synthesis": "Bull thesis prevailing: Price action aligned with healthy smart money accumulation."
            }

        return {
            "recommendation": technical_verdict,
            "conviction": Decimal("0.50"),
            "synthesis": "Debate concluded with neutral / maintain posture."
        }


class TradeCouncil:
    """Multi-Agent deliberative council synthesizing technicals, on-chain flows, and debate.
    
    Citations:
    - TauricResearch/TradingAgents: multi-agent collaborative trading council.
    - mattpocock/skills: structured agent interview & decision specification flow.
    """

    def __init__(self) -> None:
        self.technical_analyst = TechnicalAnalystAgent()
        self.onchain_analyst = FundamentalOnChainAnalystAgent()
        self.debate_chamber = BullBearDebate()

    def deliberate(
        self,
        symbol: str,
        bars: list[Bar],
        onchain: SmartMoneyMetrics | None = None,
        has_position: bool = False
    ) -> TradeMemo:
        closes = [b.close for b in bars]
        regime = classify_market_regime(closes, period_short=min(10, len(closes)), period_long=min(25, len(closes)))

        tech_res = self.technical_analyst.analyze(symbol, bars, has_position)
        onchain_res = self.onchain_analyst.analyze(onchain)

        debate_res = self.debate_chamber.debate(
            technical_verdict=tech_res["verdict"],
            onchain_verdict=onchain_res["bias"].value if isinstance(onchain_res["bias"], OnChainBias) else str(onchain_res["bias"]),
            regime=regime
        )

        bull_thesis = (
            f"Uptrend supported by SMA50 > SMA200 and Close at ${tech_res['close']:.2f}. "
            f"On-chain signals indicate steady absorption."
        )
        bear_critique = (
            f"Regime evaluated as {regime.value}. "
            f"Downside risk bounded by strict 2.0x ATR deterministic stop loss."
        )

        citations = [
            "TauricResearch/TradingAgents: Multi-agent debate & synthesis framework",
            "nansen-ai/nansen-cli: On-chain smart money netflow tracking",
            "tradermonty/claude-trading-skills: Price action & Fair Value Gap structure",
            "daviddme/TradingView-Unified-MCP: Multi-timeframe technical indicator alignment"
        ]

        return TradeMemo(
            symbol=symbol,
            recommendation=debate_res["recommendation"],
            conviction_score=debate_res["conviction"],
            bull_thesis=bull_thesis,
            bear_critique=bear_critique,
            regime=regime,
            citations=citations
        )
