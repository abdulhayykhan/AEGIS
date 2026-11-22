---
name: onchain-intelligence
description: Analysis of on-chain smart money flows, exchange reserves, and whale accumulation to validate or veto trading setups.
---

# On-Chain Intelligence Skill

**Prepared by [Abdul Hayy Khan](https://abdulhayykhan.dev)**  
*Inspired by nansen-ai/nansen-cli and agiprolabs/claude-trading-skills.*

This skill specifies the ingestion, normalization, and evaluation of on-chain market intelligence in AEGIS.

---

## 1. When to Use
- Invoked by the `FundamentalOnChainAnalystAgent` during the multi-agent council deliberation.
- Used to verify whether institutional capital is accumulating or distributing before entering a position.

---

## 2. Four-Part Run Brief

- **Outcome**: A deterministic `OnChainBias` classification (`ACCUMULATION_BULLISH`, `DISTRIBUTION_BEARISH`, `NEUTRAL`) backed by exchange netflow metrics and whale wallet tracking.
- **Context**: Ingested on-chain data from RPC nodes, Nansen CLI feeds, and DEX liquidity pool telemetry.
- **Format**: Schema-validated `SmartMoneyMetrics` model in `src/signals/onchain.py`.
- **Constraints**:
  - High exchange inflows (> +$10,000,000 USD netflow) indicate acute sell pressure; technical buy signals MUST be vetoed.
  - Large exchange outflows (< -$10,000,000 USD netflow) paired with high whale accumulation (> 70/100) corroborate bullish conviction.

---

## 3. Decision Matrix

```
       Exchange Netflow < -$10M (Outflows)
               │
               ▼
     Whale Accumulation > 70? ──► YES ──► ACCUMULATION_BULLISH (Boost Conviction)
               │
               ▼ NO
            NEUTRAL
```

```
       Exchange Netflow > +$10M (Inflows)
               │
               ▼
     Whale Accumulation < 40? ──► YES ──► DISTRIBUTION_BEARISH (Veto All Buys!)
               │
               ▼ NO
            NEUTRAL
```

---

## 4. Citations & Attribution
- **nansen-ai/nansen-cli**: CLI and programmatic interface for querying smart money movements, token god modes, wallet profilers, and exchange netflow analytics.
- **agiprolabs/claude-trading-skills**: On-chain sentiment aggregation and whale flow synthesis.
