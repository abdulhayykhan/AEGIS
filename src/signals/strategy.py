"""AEGIS Unified Strategy Engine.

Built by [Abdul Hayy Khan](https://abdulhayykhan.dev).
Citations & inspirations:
- AEGIS Project Review Report (Finding H4: Strategy Parameter Convergence)
- TradingAgents (TauricResearch): Multi-timeframe trend and regime convergence
- TradingView Technical Indicators (daviddme/TradingView-Unified-MCP)
"""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from src.signals.indicators import calculate_atr, calculate_sma, compute_trend_signal
from src.signals.models import Bar, SignalType
from src.signals.regime import MarketRegime, classify_market_regime


class StrategyConfig(BaseModel):
    """Unified configuration for AEGIS trend-following strategy across live and backtest."""
    model_config = ConfigDict(frozen=True)

    fast_period: int = Field(default=50, description="Short/fast SMA period")
    slow_period: int = Field(default=200, description="Long/slow SMA period")
    atr_period: int = Field(default=14, description="Average True Range period for stops/volatility")
    min_warmup_bars: int = Field(default=20, description="Minimum bars required before computing indicators")
    regime_filter_enabled: bool = Field(default=True, description="Filter trades during hostile regimes")
    atr_stop_multiplier: Decimal = Field(default=Decimal("2.0"), description="ATR stop distance multiplier")
    atr_take_profit_multiplier: Decimal = Field(default=Decimal("4.0"), description="ATR take-profit multiplier")


class StrategySignal(BaseModel):
    """Unified signal result providing mathematical decision rationale."""
    model_config = ConfigDict(frozen=True)

    signal: SignalType
    current_close: Decimal
    sma_fast: Decimal | None = None
    sma_slow: Decimal | None = None
    atr: Decimal | None = None
    regime: MarketRegime = MarketRegime.RANGING
    conviction: Decimal = Decimal("0.50")
    reason: str = ""


def evaluate_strategy(
    bars: list[Bar],
    has_position: bool,
    config: StrategyConfig | None = None
) -> StrategySignal:
    """Evaluate unified strategy logic across live loop and backtest engines.
    
    Guarantees zero divergence between backtest assumptions and live execution (Finding H4).
    """
    cfg = config or StrategyConfig()
    if len(bars) < cfg.min_warmup_bars:
        current_close = bars[-1].close if bars else Decimal(0)
        return StrategySignal(
            signal=SignalType.NEUTRAL,
            current_close=current_close,
            reason=f"Insufficient history: {len(bars)} bars < {cfg.min_warmup_bars} required."
        )

    closes = [b.close for b in bars]
    current_close = closes[-1]

    # Dynamically adapt period if warmup bars available are between min_warmup_bars and full period
    eff_fast = min(cfg.fast_period, max(5, len(closes) // 3))
    eff_slow = min(cfg.slow_period, max(10, (len(closes) * 2) // 3))
    eff_atr = min(cfg.atr_period, max(3, len(bars) // 4))

    sma_fast = calculate_sma(closes, period=eff_fast)
    sma_slow = calculate_sma(closes, period=eff_slow)
    atr = calculate_atr(bars, period=eff_atr)

    regime = classify_market_regime(closes, period_short=eff_fast, period_long=eff_slow)

    # Base trend signal
    signal = compute_trend_signal(
        current_close=current_close,
        sma_50=sma_fast,
        sma_200=sma_slow,
        has_position=has_position
    )

    conviction = Decimal("0.50")
    reason = f"Trend evaluation with SMA({eff_fast}) and SMA({eff_slow}). Regime={regime.value}."

    # Regime gating: In high volatility or bear regimes, suppress risk-adding entries
    if cfg.regime_filter_enabled and signal == SignalType.BUY:
        if regime in (MarketRegime.HIGH_VOLATILITY, MarketRegime.TRENDING_BEAR):
            signal = SignalType.NEUTRAL
            reason = f"Entry suppressed by Regime Gate: market in {regime.value}."
            conviction = Decimal("0.20")
        elif regime == MarketRegime.TRENDING_BULL:
            conviction = Decimal("0.85")
            reason = f"Strong trend alignment: price above SMA({eff_fast}) and SMA({eff_slow}) in {regime.value}."

    return StrategySignal(
        signal=signal,
        current_close=current_close,
        sma_fast=sma_fast,
        sma_slow=sma_slow,
        atr=atr,
        regime=regime,
        conviction=conviction,
        reason=reason
    )
