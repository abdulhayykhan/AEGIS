# AEGIS Authority Envelope

> **Four-Rung Autonomy Ladder: Observe -> Recommend -> Draft -> Execute** (Book Ch. 7.2, 7.3)  
> **Guarded File**: Protected by CODEOWNERS. The AI coding agent is forbidden to modify this file without an explicit owner instruction and reviewed pull request.

---

## 1. Authority Ladder by Phase

The authority envelope dictates the boundary of permitted autonomous action at each evolutionary stage of the agent. A trade carries direct financial risk and is difficult or impossible to reverse; therefore, authority is earned sequentially through empirical evidence, never assumed.

| Action | Phase 0-3 (Spec, Data, Backtest, Risk Gate) | Phase 4-6 (Connector & Paper Trading) | Phase 7 (Small Live with Approval) | Phase 8 (Mature Live / Target State) |
|---|---|---|---|---|
| **Read market data, news, records** | **Execute** | **Execute** | **Execute** | **Execute** |
| **Write to DB and logs** | **Execute** | **Execute** | **Execute** | **Execute** |
| **Propose a trade** | **Recommend** | **Recommend** | **Recommend** | **Recommend** |
| **Place paper orders** | **No** | **Execute inside limits** | *n/a* | *n/a* |
| **Place live orders** | **No** | **No** | **Draft** (Owner approves each order) | **Execute inside limits** (No per-trade approval) |
| **Cancel own open orders** | **No** | **Execute** | **Execute** | **Execute** |
| **Close all positions (Kill Switch)** | **Owner only** | **Owner and Risk Gate** | **Owner and Risk Gate** | **Owner and Risk Gate** |
| **Change limits, permissions, contract, strategy** | **NEVER** | **NEVER** | **NEVER** | **NEVER** |
| **Withdraw, transfer, margin, leverage** | **NEVER** | **NEVER** | **NEVER** | **NEVER** |

---

## 2. Autonomy Architecture & Target State

AEGIS targets full autonomy (**Phase 8**): autonomous trade decision, order placement, stop adjustments, and position exits with zero per-trade human intervention.

Autonomy in AEGIS means **no per-trade human approval bottlenecks**, NOT an absence of deterministic limits. Three immutable controls remain outside the AI model indefinitely:

1. **Deterministic Risk Gate (DSoR)**:
   - External Python program enforcing mathematical risk thresholds before any order reaches the exchange or broker.
   - The AI cannot inspect, bypass, or mutate these limits.
2. **Automated Self-Halting**:
   - The system immediately halts on: daily loss breach (2%), drawdown breach (10%), stale market data (> 2 bars old), reconciliation mismatch between database ledger and broker, or runaway cost.
   - The agent cannot clear a halt or resume trading. Only [Abdul Hayy Khan](https://abdulhayykhan.dev) can clear a halt after reviewing the incident log.
3. **Supervision by Exception**:
   - [Abdul Hayy Khan](https://abdulhayykhan.dev) supervises through high-signal Telegram alerts, daily summary reports, and heartbeat checks rather than tedious manual approvals.

---

## 3. Promotion Criteria Between Rungs

Promotion from one rung to the next is strictly gated by the exit criteria outlined in Section 17 of `docs/prd.md`:
- **Phase 0 -> Phase 1**: Owner signs the 5 spec files; comprehensive test list committed.
- **Phase 1 -> Phase 2**: Ingestion and signals library pass 100% unit tests; deterministic replay verified.
- **Phase 2 -> Phase 3**: Honest backtest report (with fees/slippage, zero look-ahead) reviewed by owner.
- **Phase 3 -> Phase 4**: 100% pass on gate unit tests, property tests, and planted-bug tests; kill switch operational while agent is stopped.
- **Phase 4 -> Phase 5**: MCP connector verified via MCP Inspector and contract tests; zero forbidden tools exist.
- **Phase 5 -> Phase 6**: 2 weeks of live runs in Recommend-Only mode; red-team tests pass; independent recomputation matches.
- **Phase 6 -> Phase 7**: At least 8 consecutive weeks of paper trading with zero limit violations and daily reconciliation matches.
- **Phase 7 -> Phase 8**: At least 4 weeks of small live trading with owner approval, zero violations, and slippage matching backtest models.

---

## 4. Owner Sign-off & Current Phase

- **Active Phase**: Phase 0 (Specification)
- **Active Rung for Orders**: **NO EXECUTION** (Phase 0)
- **Owner Signature**: `[PENDING OWNER SIGNATURE: [Abdul Hayy Khan](https://abdulhayykhan.dev)]`
- **Date**: 2026-11-22
