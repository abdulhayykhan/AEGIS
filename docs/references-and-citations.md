# Open-Source References, Architectural Citations & Integration Guide

**Prepared by [Abdul Hayy Khan](https://abdulhayykhan.dev)**  
**Repository**: [https://github.com/abdulhayykhan/AEGIS](https://github.com/abdulhayykhan/AEGIS)  
**Specification**: AEGIS Autonomous Trading Digital FTE  

---

## Executive Summary

To elevate AEGIS to an institutional standard of intelligence, multi-agent collaboration, and execution rigor, eight world-class open-source projects were analyzed and deeply integrated into the AEGIS codebase. 

While the reasoning engine has been significantly upgraded with specialized agent roles, price action indicators, on-chain smart money tracking, and multi-timeframe consensus, **AEGIS's immutable security boundary is strictly preserved**:
> All multi-agent deliberation, price action patterns, and on-chain intelligence culminate in schema-validated trade proposals that must pass the 8 deterministic checks of the Risk Gate (DSoR) before any order can ever reach a broker.

---

## Detailed Citations & Architectural Mapping

### 1. TauricResearch / TradingAgents
- **URL**: [https://github.com/TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents)
- **Role in AEGIS**: Multi-Agent Council & Deliberation Architecture
- **Integrated Files**:
  - [`src/agent/council.py`](file:///c:/Users/USER/Desktop/AEGIS/src/agent/council.py) (`TechnicalAnalystAgent`, `FundamentalOnChainAnalystAgent`, `BullBearDebate`, `TradeCouncil`, `TradeMemo`)
  - [`src/agent/loop.py`](file:///c:/Users/USER/Desktop/AEGIS/src/agent/loop.py) (`AgentConfig.enable_council`)
  - [`skills/multi-agent-debate/SKILL.md`](file:///c:/Users/USER/Desktop/AEGIS/skills/multi-agent-debate/SKILL.md)
  - [`tests/unit/test_agent_council.py`](file:///c:/Users/USER/Desktop/AEGIS/tests/unit/test_agent_council.py)
- **Contribution**: Replaces brittle, monolithic single-prompt agent reasoning with specialized agent roles. A technical analyst, on-chain analyst, bull researcher, and bear risk advocate debate candidate setups. The bear advocate possesses veto power: if on-chain distribution is active, technical buy signals are aborted, preventing false breakout entries.

---

### 2. tradermonty / claude-trading-skills
- **URL**: [https://github.com/tradermonty/claude-trading-skills](https://github.com/tradermonty/claude-trading-skills)
- **Role in AEGIS**: Institutional Price Action & Liquidity Structure
- **Integrated Files**:
  - [`src/signals/price_action.py`](file:///c:/Users/USER/Desktop/AEGIS/src/signals/price_action.py) (`detect_fair_value_gaps`, `FairValueGap`)
  - [`skills/price-action-and-liquidity/SKILL.md`](file:///c:/Users/USER/Desktop/AEGIS/skills/price-action-and-liquidity/SKILL.md)
  - [`tests/unit/test_price_action.py`](file:///c:/Users/USER/Desktop/AEGIS/tests/unit/test_price_action.py)
- **Contribution**: Adapts Inner Circle Trader (ICT) concepts into deterministic Python functions. Identifies 3-bar displacement imbalances (Fair Value Gaps, FVGs) to time order entries into high-liquidity zones rather than chasing extended breakouts.

---

### 3. nansen-ai / nansen-cli
- **URL**: [https://github.com/nansen-ai/nansen-cli](https://github.com/nansen-ai/nansen-cli)
- **Role in AEGIS**: Smart Money Tracking & On-Chain Exchange Netflow Intelligence
- **Integrated Files**:
  - [`src/signals/onchain.py`](file:///c:/Users/USER/Desktop/AEGIS/src/signals/onchain.py) (`SmartMoneyMetrics`, `OnChainBias`, `compute_smart_money_bias`)
  - [`src/connector/server.py`](file:///c:/Users/USER/Desktop/AEGIS/src/connector/server.py) (`get_onchain_flow` tool)
  - [`skills/onchain-intelligence/SKILL.md`](file:///c:/Users/USER/Desktop/AEGIS/skills/onchain-intelligence/SKILL.md)
  - [`tests/unit/test_onchain_and_tv.py`](file:///c:/Users/USER/Desktop/AEGIS/tests/unit/test_onchain_and_tv.py)
- **Contribution**: Provides institutional crypto intelligence by monitoring whale wallet accumulation scores and net token transfers into/out of centralized exchanges. If smart money is aggressively depositing to exchanges (distribution), AEGIS automatically vetoes buy proposals.

---

### 4. agiprolabs / claude-trading-skills
- **URL**: [https://github.com/agiprolabs/claude-trading-skills](https://github.com/agiprolabs/claude-trading-skills)
- **Role in AEGIS**: Market Regime Classification & Adaptive Volatility Gating
- **Integrated Files**:
  - [`src/signals/regime.py`](file:///c:/Users/USER/Desktop/AEGIS/src/signals/regime.py) (`MarketRegime`, `classify_market_regime`)
  - [`skills/market-regime-detection/SKILL.md`](file:///c:/Users/USER/Desktop/AEGIS/skills/market-regime-detection/SKILL.md)
  - [`tests/unit/test_agent_council.py`](file:///c:/Users/USER/Desktop/AEGIS/tests/unit/test_agent_council.py)
- **Contribution**: Implements deterministic market state categorization into `TRENDING_BULL`, `TRENDING_BEAR`, `RANGING`, and `HIGH_VOLATILITY`. Trend strategies are automatically gated during choppy consolidation phases, cutting whipsaw losses.

---

### 5. marian2js / trading-skills
- **URL**: [https://github.com/marian2js/trading-skills](https://github.com/marian2js/trading-skills)
- **Role in AEGIS**: Technical Indicator Toolkit & Multi-Timeframe Confirmation
- **Integrated Files**:
  - [`src/signals/price_action.py`](file:///c:/Users/USER/Desktop/AEGIS/src/signals/price_action.py) (`calculate_rsi`, `calculate_bollinger_bands`)
  - [`src/signals/multitimeframe.py`](file:///c:/Users/USER/Desktop/AEGIS/src/signals/multitimeframe.py) (`check_multitimeframe_trend_alignment`)
  - [`tests/unit/test_price_action.py`](file:///c:/Users/USER/Desktop/AEGIS/tests/unit/test_price_action.py)
- **Contribution**: Provides Wilder's smoothed Relative Strength Index (RSI), Bollinger Bandwidth / %B metrics, and multi-timeframe trend filters (1D macro trend combined with 4H execution alignment).

---

### 6. mattpocock / skills
- **URL**: [https://github.com/mattpocock/skills](https://github.com/mattpocock/skills)
- **Role in AEGIS**: Modular Agent Skill Architecture & Production Protocols
- **Integrated Files**:
  - [`skills/multi-agent-debate/SKILL.md`](file:///c:/Users/USER/Desktop/AEGIS/skills/multi-agent-debate/SKILL.md)
  - [`skills/market-regime-detection/SKILL.md`](file:///c:/Users/USER/Desktop/AEGIS/skills/market-regime-detection/SKILL.md)
  - [`skills/onchain-intelligence/SKILL.md`](file:///c:/Users/USER/Desktop/AEGIS/skills/onchain-intelligence/SKILL.md)
  - [`skills/price-action-and-liquidity/SKILL.md`](file:///c:/Users/USER/Desktop/AEGIS/skills/price-action-and-liquidity/SKILL.md)
  - [`skills/incident-postmortem/SKILL.md`](file:///c:/Users/USER/Desktop/AEGIS/skills/incident-postmortem/SKILL.md)
  - [`skills/trading-run/SKILL.md`](file:///c:/Users/USER/Desktop/AEGIS/skills/trading-run/SKILL.md)
- **Contribution**: Establishes standard YAML-frontmattered, markdown-based skill specifications with strict "Four-Part Run Briefs" (Outcome, Context, Format, Constraints), step-by-step procedures, and blameless postmortem templates.

---

### 7. daviddme / TradingView-Unified-MCP
- **URL**: [https://github.com/daviddme/TradingView-Unified-MCP](https://github.com/daviddme/TradingView-Unified-MCP)
- **Role in AEGIS**: Standardized MCP Technical Tools & Charting Parity
- **Integrated Files**:
  - [`src/connector/server.py`](file:///c:/Users/USER/Desktop/AEGIS/src/connector/server.py) (`get_technical_summary` MCP tool)
  - [`tests/contract/test_mcp_connector.py`](file:///c:/Users/USER/Desktop/AEGIS/tests/contract/test_mcp_connector.py)
- **Contribution**: Exposes standardized technical indicator summaries over MCP, aligning internal Python calculations with institutional TradingView charting standards.

---

### 8. daviddme / tradingview-indicator-search-mcp-server
- **URL**: [https://github.com/daviddme/tradingview-indicator-search-mcp-server](https://github.com/daviddme/tradingview-indicator-search-mcp-server)
- **Role in AEGIS**: Indicator Metadata Schema & PineScript Mapping
- **Integrated Files**:
  - [`src/connector/server.py`](file:///c:/Users/USER/Desktop/AEGIS/src/connector/server.py)
  - [`docs/references-and-citations.md`](file:///c:/Users/USER/Desktop/AEGIS/docs/references-and-citations.md)
- **Contribution**: Provides metadata conventions for PineScript indicators and technical summaries, allowing agents to query technical summaries across timeframes with zero ambiguity.

---

## Verification & Architecture Review

Every integrated component is subjected to strict unit, property, and contract testing:
- **Zero Hallucination**: No indicator or sizing parameter is ever generated freehand by an LLM prompt; every value is computed by tested functions in `src/signals/`.
- **DSoR Enforced**: The multi-agent council produces a `TradeMemo` which feeds into `OrderProposal`. The Risk Gate independently evaluates daily loss limits, instrument allowlists, notional order caps, cash buffers, and slippage before execution.
- **Full Test Coverage**: The integration is verified by 88+ automated tests in `pytest`.
