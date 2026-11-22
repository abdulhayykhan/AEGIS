# AGENTS.md: Rules for the AEGIS Coding Agent

> Based on *The AI Agent Factory (Panaversity)*, v2.
> Repository: https://github.com/abdulhayykhan/AEGIS
> Owner: Abdul Hayy

This file establishes the immutable operating laws, safety constraints, and development protocol for any AI coding agent working on the AEGIS codebase.

---

## 1. Core Operating Principles

1. **Phased Build Order**:
   - Always build in the strict phase sequence defined in Section 17 of `docs/prd.md`.
   - Never begin a phase until the previous phase's exit criteria pass with verifiable evidence.
2. **Test-Driven Governance (TDG)**:
   - For every rule in Sections 7 (Risk Gate), 9 (Connector/MCP), and 11 (Strategy & Signals), write the test first, observe it fail, and then write the code to satisfy it (Book Ch. 13.11).
   - "Done" means evidence: passing test suites, backtest reports, audit records, and reconciliation proofs. Never claim "it ran".
3. **Permissions, Not Words**:
   - Any limit or safety boundary must be enforced in deterministic code or system settings outside the model.
   - Prompts that say "never do X" are not controls. The model is an untrusted reasoning engine; the Risk Gate (DSoR) is the deterministic enforcer.
4. **Authority Envelope is Sacred**:
   - The coding agent must never widen the Authority Envelope (`docs/authority-envelope.md`) on its own.
   - Promotion across autonomy rungs (Observe -> Recommend -> Draft -> Execute) requires explicit owner sign-off and reviewed pull requests.
5. **Honor [OWNER DECISION]**:
   - Where the PRD or codebase specifies `[OWNER DECISION]`, stop and ask the owner (Abdul Hayy). Do not guess or assume.
6. **Separation of Concerns & Untrusted Input**:
   - Market news, external text, and web inputs are completely untrusted.
   - Summarization occurs in read-only workflows with no order tools.
   - Order pathways accept only structured, schema-validated proposals backed by verifiable mathematical evidence.
7. **No Broker Credentials in the Model**:
   - The model harness never holds broker API keys or execution secrets.
   - Only the deterministic Risk Gate / Connector layer holds execution credentials. Broker keys must be strictly trade-only with withdrawals and transfers disabled at the venue.

---

## 2. Guarded Files & Permissions (CODEOWNERS)

The following paths represent the security boundary of the system:
- `src/gate/` (The Risk Gate)
- `docs/role-contract.md`
- `docs/authority-envelope.md`
- `docs/risk-policy.md`

**Agent Rule**: The agent must NEVER edit these files without explicit, recorded owner instruction in the active task, and all modifications must be made via reviewed pull requests.

---

## 3. Standard Task Workflow

At the start of each task/phase:
1. Read `AGENTS.md` and the relevant spec files in `docs/`.
2. Restate the phase goal, scope, and specific exit criteria.
3. Write failing unit, property, or contract tests before writing production implementation.
4. Run the test suite and verify failures.
5. Implement the minimal clean code to make tests pass.
6. Verify against all exit criteria and regression checks.
7. Report:
   - What was changed and why.
   - Which tests were executed and their exact outputs.
   - What could not be automatically verified.
   - What the owner must decide next.
