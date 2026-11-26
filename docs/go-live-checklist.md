# AEGIS Go-Live Checklist (Phase 7 Gate)

> Based on *The AI Agent Factory (Panaversity)*, Ch. 18.  
> Status: **PAPER HARNESS CONTROLS VERIFIED — LIVE ADAPTER & VENUE PREREQUISITES REQUIRED BEFORE REAL CAPITAL**  
> Target Owner: [Abdul Hayy Khan](https://abdulhayykhan.dev) (`@abdulhayykhan`)

Before transitioning AEGIS from Paper Trading (Phase 6) to Small Live with Approval (Phase 7) or Full Autonomy (Phase 8), each item in this checklist must be rigorously audited and verified with empirical evidence.

---

## 1. Governance & Authority Boundaries (Code-Enforced)
- [x] **Role Contract Signed**: `docs/role-contract.md` signed by owner; digital FTE mandate locked.
- [x] **Authority Envelope Enforced**: Rung 3 (Draft / Owner Approves Each Order via cryptographic signature with expiry & single-use nonce) strictly enforced in `RiskGate`.
- [x] **CODEOWNERS Enforced**: CODEOWNERS configuration protecting security perimeter (`src/gate/`, `src/connector/`, `ops/`, specs).
- [x] **No LLM in Gate**: Risk Gate (DSoR) is 100% deterministic external Python logic.

## 2. API Security & Venue Permissions (Venue-Side Operational Prerequisites)
- [ ] **Trade-Only Keys**: Execution credentials restricted to Spot Trading only at exchange portal.
- [ ] **Withdrawals Disabled**: Transfer and withdrawal API permissions permanently disabled at the exchange/broker venue.
- [ ] **IP Whitelisting**: Broker API keys restricted to authorized runner IP ranges.
- [x] **No Keys in Prompts**: Zero broker secrets or private keys exposed to LLM context or repository code.

## 3. Capital & Risk Allocation (Code-Enforced & Operational)
- [ ] **Tiny Live Capital**: Initial live venue allocation limited to maximum $500.00 USDT *(operational/venue cap — not enforced in code; `PaperBroker` defaults to $10,000.00)*.
- [x] **Per-Trade Risk & Max Position**: Hard cap at 1.0% equity risk per trade (`max_risk_pct = 0.01`) and 10.0% max position notional per instrument (`max_position_pct = 0.10`).
- [x] **Daily Loss & Order Count Limits**: Deterministic halt at 2.0% equity loss (`max_daily_loss_pct = 0.02`) and 10 non-exempt orders per UTC day (`max_orders_per_day = 10`).
- [x] **Max Drawdown Limit**: Deterministic halt at 10.0% peak drawdown (`max_drawdown_pct = 0.10`).

## 4. Emergency Kill Switch & Self-Halting (Code-Enforced)
- [x] **Manual Kill Switch**: Accessible via CLI, file lock (`data/aegis_kill_switch.lock`), and connector.
- [x] **Automated Self-Halting**: Triggers automatically on daily loss breach, drawdown breach, stale data (> 2 bars), or reconciliation discrepancy.
- [x] **Test Verification**: Planted-bug, kill switch wiring, and CLI lock unit tests verified passing.

## 5. Operations, Scheduling & Monitoring (Code-Enforced)
- [x] **Single-Process Locking**: Process lock (`scheduler.lock`) with automated stale-lock recovery prevents overlapping runs.
- [x] **Ran is Not Worked**: All 6 post-flight checks mandatory before marking cycle success.
- [x] **Alerting Configured**: Telegram alerts dispatcher and dead-man's switch heartbeat tracking implemented (`ops/alerts.py`).
- [x] **Operations Dashboard**: Real-time CLI / Markdown status dashboard active (`ops/dashboard.py`).

## 6. Empirical Evidence & Harness Audits
- [x] **Zero Look-Ahead Backtest**: Simulation with pessimistic 0.10% fees, 0.05% slippage, gap-through stop modeling, and future bar mutation invariance completed (`docs/backtest-report.md`).
- [x] **Paper Trading Scaffolding**: 56 consecutive days simulated in test harness with 0 risk violations and 100% daily reconciliation matches (`docs/paper-execution-report.md`). Awaiting real multi-week calendar testnet run.
- [x] **Red-Team Injection Suite**: 100% defense against prompt injection attacks with active quarantine (`tests/redteam/test_prompt_injection.py`).

---

## 7. Owner Sign-Off & Activation Record

| Gate Parameter | Owner Decision / Value |
|---|---|
| **Authorizing Owner** | [Abdul Hayy Khan](https://abdulhayykhan.dev) |
| **Active Target Phase** | Phase 7: Small Live with Approval |
| **Capital Allocation** | $500.00 USDT |
| **Owner Approval Mechanism** | Canonical HMAC-SHA256 / Ed25519 Signature (`AEGIS_APPROVAL_SECRET` / `AEGIS_APPROVAL_PUBLIC_KEY`) |
| **Go-Live Date** | `[OWNER CONFIRMATION PENDING]` |
