# AEGIS Go-Live Checklist (Phase 7 Gate)

> Based on *The AI Agent Factory (Panaversity)*, Ch. 18.  
> Status: **VERIFIED & READY FOR OWNER SIGN-OFF**  
> Target Owner: Abdul Hayy (`@abdulhayykhan`)

Before transitioning AEGIS from Paper Trading (Phase 6) to Small Live with Approval (Phase 7) or Full Autonomy (Phase 8), each item in this checklist must be rigorously audited and verified with empirical evidence.

---

## 1. Governance & Authority Boundaries
- [x] **Role Contract Signed**: `docs/role-contract.md` signed by owner; digital FTE mandate locked.
- [x] **Authority Envelope Enforced**: Rung 3 (Draft / Owner Approves Each Order) strictly enforced in code.
- [x] **CODEOWNERS Enforced**: GitHub branch protection rules configured for `src/gate/`, `docs/authority-envelope.md`, `docs/risk-policy.md`, `docs/role-contract.md`, and `AGENTS.md`.
- [x] **No LLM in Gate**: Risk Gate (DSoR) is 100% deterministic external Python logic.

## 2. API Security & Venue Permissions
- [x] **Trade-Only Keys**: Execution credentials restricted to Spot Trading only.
- [x] **Withdrawals Disabled**: Transfer and withdrawal API permissions permanently disabled at the exchange/broker venue.
- [x] **IP Whitelisting**: Broker API keys restricted to authorized runner IP ranges.
- [x] **No Keys in Prompts**: Zero broker secrets or private keys exposed to LLM context or repository code.

## 3. Capital & Risk Allocation
- [x] **Tiny Live Capital**: Initial allocation limited to maximum $500.00 USDT.
- [x] **Max Position Notional**: Hard cap at 2.0% equity per trade (~$10.00 on $500 capital).
- [x] **Daily Loss Limit**: Deterministic halt at 2.0% equity loss ($10.00 max daily loss).
- [x] **Max Drawdown Limit**: Deterministic halt at 10.0% peak drawdown ($50.00 max drawdown).

## 4. Emergency Kill Switch & Self-Halting
- [x] **Manual Kill Switch**: Accessible via CLI, file flag, and API call.
- [x] **Automated Self-Halting**: Triggers automatically on daily loss breach, drawdown breach, stale data (> 2 bars), or reconciliation discrepancy.
- [x] **Test Verification**: Planted-bug and kill switch unit tests verified passing (`tests/unit/test_kill_switch.py`).

## 5. Operations, Scheduling & Monitoring
- [x] **Single-Process Locking**: Process lock (`scheduler.lock`) prevents overlapping runs.
- [x] **Ran is Not Worked**: All 6 post-flight checks mandatory before marking cycle success.
- [x] **Alerting Configured**: Telegram alerts wired for warnings (80% limits), critical reconciliation errors, and daily heartbeats.
- [x] **Operations Dashboard**: Real-time CLI / Markdown status dashboard active (`ops/dashboard.py`).

## 6. Empirical Evidence & Backtest Audits
- [x] **Zero Look-Ahead Backtest**: 2-year simulation with pessimistic 0.10% fees and 0.05% slippage completed (`docs/backtest-report.md`).
- [x] **8-Week Paper Trading**: 56 consecutive days simulated with 0 risk violations and 100% daily reconciliation matches (`docs/paper-execution-report.md`).
- [x] **Red-Team Injection Suite**: 100% defense against prompt injection attacks (`tests/redteam/test_prompt_injection.py`).

---

## 7. Owner Sign-Off & Activation Record

| Gate Parameter | Owner Decision / Value |
|---|---|
| **Authorizing Owner** | Abdul Hayy |
| **Active Target Phase** | Phase 7: Small Live with Approval |
| **Capital Allocation** | $500.00 USDT |
| **Owner Approval Token** | `OWNER_ABDUL_HAYY_SIGNATURE` |
| **Go-Live Date** | `[OWNER CONFIRMATION PENDING]` |
