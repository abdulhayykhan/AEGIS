---
name: price-action-and-liquidity
description: Price action structural analysis covering ICT Fair Value Gaps (FVG), Bollinger Bands, Wilder's RSI, and multi-timeframe alignment.
---

# Price Action & Liquidity Skill

**Prepared by [Abdul Hayy Khan](https://abdulhayykhan.dev)**  
*Inspired by tradermonty/claude-trading-skills, marian2js/trading-skills, and daviddme/TradingView-Unified-MCP.*

This skill defines the technical analysis framework for institutional order flow, liquidity imbalances, and price action indicators.

---

## 1. When to Use
- Executed during the technical screening stage of each cycle by `TechnicalAnalystAgent`.
- Pinpoints high-probability entry zones (liquidity imbalances) instead of entering naively at arbitrary market prices.

---

## 2. Four-Part Run Brief

- **Outcome**: Identified Fair Value Gaps (FVGs), Bollinger Band expansion metrics (%B, bandwidth), and Wilder's smoothed RSI momentum values.
- **Context**: 30 to 100 historical OHLCV bars across 1D and 4H timeframes.
- **Format**: Structured list of `FairValueGap` records and `BollingerBands` data classes.
- **Constraints**:
  - Imbalance gaps must be validated by 3-bar displacement price geometry.
  - Wilder's exponential smoothing is mandatory for RSI to eliminate noise.

---

## 3. Structural Components

### 1. Fair Value Gaps (FVG)
- **Bullish FVG**: Occurs during an energetic upward move where `bar[i-2].high < bar[i].low`. The unfilled space between the wick of bar 1 and the wick of bar 3 represents an institutional imbalance.
- **Bearish FVG**: Occurs during an energetic downward move where `bar[i-2].low > bar[i].high`.

### 2. Bollinger Bandwidth & Squeeze
- Bandwidth $< 0.10$ indicates volatility compression (a "squeeze") preceding explosive directional expansion.
- Bandwidth expansion combined with `%B > 0.80` confirms strong upward momentum.

### 3. Multi-Timeframe Alignment
- Higher timeframe (1D) sets the macro bias: `SMA_50 > SMA_200`.
- Lower timeframe (4H) provides optimal entry refinement: price retracing into a Bullish FVG or bouncing off lower Bollinger Band.

---

## 4. Citations & Attribution
- **tradermonty/claude-trading-skills**: Systematic implementation of Inner Circle Trader (ICT) concepts, Fair Value Gaps, liquidity sweeps, and price action trading.
- **marian2js/trading-skills**: Quantitative price action indicators, volatility breakout filters, and multi-timeframe confirmations.
- **daviddme/TradingView-Unified-MCP**: Unified indicator calculation and charting parity.
