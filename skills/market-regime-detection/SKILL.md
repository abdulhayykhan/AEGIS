---
name: market-regime-detection
description: Systematic classification of market regimes (trending, ranging, high volatility) to dynamically condition trading strategies and sizing.
---

# Market Regime Detection Skill

**Prepared by [Abdul Hayy Khan](https://abdulhayykhan.dev)**  
*Inspired by agiprolabs/claude-trading-skills, marian2js/trading-skills, and daviddme/TradingView-Unified-MCP.*

This skill establishes the deterministic classification and operational protocol for market regimes in AEGIS.

---

## 1. When to Use
- Run at the start of each bar evaluation prior to computing strategy signals.
- Injects market state awareness into the deliberative multi-agent council.
- Gates trend-following entry triggers when the asset is oscillating in a choppy range.

---

## 2. Four-Part Run Brief

- **Outcome**: A deterministic `MarketRegime` enum state (`TRENDING_BULL`, `TRENDING_BEAR`, `RANGING`, `HIGH_VOLATILITY`).
- **Context**: Recent OHLCV bars across daily (1D) and 4-hour (4H) timeframes.
- **Format**: Structured enum with indicator evidence (SMA differential %, ATR percentile, Bollinger Bandwidth).
- **Constraints**:
  - Zero subjective guesswork: thresholds are evaluated using tested mathematical functions in `src/signals/regime.py`.
  - Strategy switching: Trend strategies are throttled or withheld in `RANGING` or `HIGH_VOLATILITY` regimes.

---

## 3. Classification Criteria

| Market Regime | Mathematical Conditions | Action / Strategy Impact |
| :--- | :--- | :--- |
| **TRENDING_BULL** | SMA(10) > SMA(30) by >= 1.0%, Close >= SMA(10) | Standard long trend proposals permitted |
| **TRENDING_BEAR** | SMA(10) < SMA(30) by >= 1.0%, Close <= SMA(10) | Long proposals strictly prohibited |
| **RANGING** | |SMA(10) - SMA(30)| / SMA(30) < 1.0% | Trend entries suppressed (Bear debate wins) |
| **HIGH_VOLATILITY** | ATR(14) > 90th percentile of 60-day historical ATR | Position sizing halved or execution suspended |

---

## 4. Citations & Attribution
- **agiprolabs/claude-trading-skills**: Adaptive market regime classification, volatility scaling, and strategy gating.
- **marian2js/trading-skills**: Multi-timeframe trend consistency and range filters.
- **daviddme/TradingView-Unified-MCP**: Technical indicator computation and multi-timeframe consensus metrics.
