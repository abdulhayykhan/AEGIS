---
name: incident-postmortem
description: Structured operational protocol for conducting root cause analyses and producing immutable incident reports following safety halts, kill switch activations, or reconciliation breaches.
---

# Incident Postmortem & Safety Review Protocol

**Prepared by [Abdul Hayy Khan](https://abdulhayykhan.dev)**  
*Inspired by mattpocock/skills and The AI Agent Factory (Panaversity) Chapter 25.*

This skill defines the mandatory protocol whenever the AEGIS system encounters a failure, halt, or automated demotion.

---

## 1. When to Use
- Triggered immediately when:
  - Emergency Kill Switch is activated (`kill_switch_active == True`).
  - Stale market data causes a cycle halt (> 2 missed bar intervals).
  - Internal database records diverge from broker balances (reconciliation mismatch).
  - Autonomy demotion event occurs (*"any safety violation drops an autonomy rung"*).

---

## 2. Four-Part Run Brief

- **Outcome**: A signed, immutable incident postmortem report stored in `docs/postmortems/YYYY-MM-DD-<slug>.md` and logged in PostgreSQL.
- **Context**: System logs, broker trade logs, database reconciliation diffs, and Risk Gate check traces.
- **Format**: Standard blameless engineering postmortem template (Summary, Impact, Timeline, Root Cause, Remediation Actions, Owner Sign-Off).
- **Constraints**:
  - Blameless: Focus strictly on code invariants, network latencies, or data integrity boundaries.
  - No resume without owner instruction: Recovery requires explicit sign-off from [Abdul Hayy Khan](https://abdulhayykhan.dev).

---

## 3. Postmortem Template

```markdown
# Incident Postmortem: [YYYY-MM-DD Title]

**Owner & Reviewer**: [Abdul Hayy Khan](https://abdulhayykhan.dev)  
**Status**: Resolved / Pending Sign-off  
**Autonomy Impact**: System Demoted to RECOMMEND_ONLY  

## 1. Incident Summary
- What occurred, when it started, and when it was detected.

## 2. Impact & Risk Assessment
- Financial impact (realized loss, slippage, unhedged exposure).
- Gate interventions (which checks failed, whether orders were blocked).

## 3. Timeline of Events (UTC)
- `HH:MM:SS` - Event detected by scheduler/monitor.
- `HH:MM:SS` - Risk Gate or Kill Switch engaged.
- `HH:MM:SS` - Owner alert dispatched.

## 4. Root Cause Analysis (5 Whys)
- Why did the anomaly occur?
- Was it data feed staleness, broker API latency, or mathematical edge case?

## 5. Corrective & Preventative Invariants
- Deterministic code patch or test case added.
- New unit/property test added to `tests/` to prevent recurrence.

## 6. Promotion Sign-off
- Signed by owner: [Abdul Hayy Khan](https://abdulhayykhan.dev)
```

---

## 4. Citations & Attribution
- **mattpocock/skills**: Structured workflow definitions and failure-handling procedures for production AI agents.
- **The AI Agent Factory (Panaversity)**: Chapter 25 (Production Operations, Monitoring, Demotions, and Postmortems).
