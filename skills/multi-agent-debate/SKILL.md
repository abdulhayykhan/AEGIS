---
name: multi-agent-debate
description: Deliberative multi-agent debate protocol between specialized technical analysts, on-chain researchers, and risk advocates prior to trade proposal synthesis.
---

# Multi-Agent Deliberation & Debate Protocol

**Prepared by [Abdul Hayy Khan](https://abdulhayykhan.dev)**  
*Inspired by TauricResearch/TradingAgents and mattpocock/skills.*

This skill defines the operational procedure for executing a structured multi-agent council deliberation before any trade proposal is generated in AEGIS.

---

## 1. When to Use
- Executed during the signal evaluation phase of each autonomous trading run.
- Activated whenever raw technical indicators indicate a candidate setup, to subject the thesis to adversarial peer review.
- Mandatory when `AgentConfig.enable_council` is active.

---

## 2. Four-Part Run Brief

- **Outcome**: A structured, evidenced `TradeMemo` containing a final recommendation (`BUY`, `SELL`, `HOLD`), conviction score (0.00 to 1.00), bull thesis, bear critique, and market regime classification.
- **Context**: OHLCV market bars, on-chain smart money flows, order book liquidity, and current account risk envelope.
- **Format**: Pydantic `TradeMemo` object with strict schema validation.
- **Constraints**:
  - Deterministic calculations only (all indicators and sizing computed by tested library code in `src/signals/`).
  - Bear risk advocate has veto authority: conflicting on-chain distribution or ranging chop immediately suppresses execution.
  - The deliberation produces an order proposal only; it NEVER bypasses the deterministic Risk Gate (DSoR).

---

## 3. Deliberation Chamber Roles

### Role 1: Technical Analyst Agent (`TechnicalAnalystAgent`)
- Computes trend direction (SMA 50 vs. SMA 200), momentum (Wilder's RSI), volatility channels (Bollinger Bands), and institutional Fair Value Gaps (FVGs).
- Emits a technical verdict: `BUY`, `SELL`, or `HOLD`.

### Role 2: Fundamental & On-Chain Analyst Agent (`FundamentalOnChainAnalystAgent`)
- Inspects exchange netflows (USD), whale wallet accumulation scores, and DEX liquidity depth (inspired by `nansen-ai/nansen-cli`).
- Classifies smart money bias: `ACCUMULATION_BULLISH`, `DISTRIBUTION_BEARISH`, or `NEUTRAL`.

### Role 3: Bull vs. Bear Adversarial Debate (`BullBearDebate`)
- The **Bull Researcher** argues for upside potential and entry timing.
- The **Bear Risk Advocate** probes for vulnerabilities, false breakouts, macro head-winds, and on-chain distribution traps.
- Invariant: If on-chain flows indicate distribution while technicals show a buy, the Bear warning wins and recommendation drops to `HOLD` with low conviction (< 0.50).

### Role 4: Trade Council Synthesis (`TradeCouncil`)
- Weighs consensus and emits the final `TradeMemo`.
- Minimum conviction threshold (e.g. 0.70) required to proceed to proposal generation.

---

## 4. Citations & Attribution
- **TauricResearch/TradingAgents**: Multi-agent collaborative trading architecture, specialized agent roles, and adversarial bull-bear debate.
- **mattpocock/skills**: Clean, modular, specification-driven skill architecture for autonomous agent systems.
