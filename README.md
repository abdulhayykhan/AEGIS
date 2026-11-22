# AEGIS: Autonomous Execution with Governed Investment Safeguards

[![AEGIS CI](https://github.com/abdulhayykhan/AEGIS/actions/workflows/ci.yml/badge.svg)](https://github.com/abdulhayykhan/AEGIS/actions/workflows/ci.yml)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **An AI Trading Digital FTE that acts on its own, inside deterministic limits it cannot change.**  
> Built by [Abdul Hayy Khan](https://abdulhayykhan.dev), following the spec-driven, human-supervised engineering practices of *The AI Agent Factory (Panaversity)*, v2.

---

## 1. What is AEGIS?

AEGIS is an autonomous digital trading worker designed to research liquid market data and news, generate mathematically grounded trade proposals, and execute trades through an exchange or broker API. 

Unlike traditional bots or raw LLM agents:
- **Hard Limits Outside the Model**: All risk checks, sizing rules, daily loss gates, and exposure caps run in deterministic Python code with **zero LLM involvement**.
- **Supervision by Exception**: The owner supervises through automated high-signal alerts and daily reconciliation reports rather than manual trade-by-trade approvals.
- **Progressive Autonomy Ladder**: Authority is earned systematically across 8 strict phases (Recommend -> Paper Execution -> Small Live -> Autonomous Live).

---

## 2. Six-Layer Architecture

AEGIS is engineered with six distinct architectural layers, ensuring strict separation between reasoning, knowledge, memory, state, and execution:

| Layer | Component | Function |
|---|---|---|
| **1. Model + Harness** | `src/agent/` | LLM reasoning engine operating in a bounded loop with strict turn, cost, and time limits. |
| **2. Skill** | `skills/trading-run/` | Standardized operating playbook (`SKILL.md`) defining the 4-part run brief and cycle flow. |
| **3. KSoR (Knows)** | `docs/` | Knowledge of Record: versioned strategy spec, risk policy, role contract, and authority envelope. |
| **4. Memory (Remembers)** | Ephemeral / Scratch | Non-authoritative contextual notes. Never the source of truth for balances or limits. |
| **5. SSoR (Tracks)** | `src/migrations/` | System of Record: PostgreSQL tracking bars, signals, proposals, orders, fills, and audit runs. |
| **6. DSoR (Acts)** | `src/gate/` & `src/connector/` | Deterministic System of Record: The Risk Gate and Broker MCP Connector enforcing all limits. |

---

## 3. Repository Structure

```
AEGIS/
├── AGENTS.md                  # Immutable operating rules for AI coding agents
├── pyproject.toml             # Python 3.12 dependencies and tooling config
├── .github/
│   ├── CODEOWNERS             # Mandatory owner review for safety files
│   └── workflows/ci.yml       # Continuous integration pipeline
├── docs/
│   ├── prd.md                 # Complete 21-page PRD and Build Guide
│   ├── role-contract.md       # Portable, owned 1-page worker contract
│   ├── authority-envelope.md  # 4-rung autonomy ladder and matrix
│   ├── risk-policy.md         # Deterministic Risk Gate specifications (DSoR)
│   ├── strategy-spec.md       # Baseline strategy specification (Dual SMA + ATR)
│   └── runbook.md             # Emergency response and operations runbook
├── skills/
│   └── trading-run/SKILL.md   # Trading cycle skill definition
├── src/
│   ├── signals/               # Tested indicator math and sizing algorithms
│   ├── gate/                  # Deterministic Risk Gate (no LLM calls)
│   ├── connector/             # MCP server providing broker and data tools
│   ├── agent/                 # Bounded agent loop and execution harness
│   ├── reports/               # Independent audit and reporting recomputation
│   └── migrations/            # Numbered PostgreSQL schema migrations
├── tests/
│   ├── test_list.md           # Master test matrix across all layers
│   ├── unit/                  # Unit tests with hand-checked answers
│   ├── property/              # Hypothesis-based invariant property tests
│   ├── contract/              # MCP tool schema and contract tests
│   ├── planted_bugs/          # Mutation tests confirming bugs break tests
│   ├── replay/                # Deterministic historical replay tests
│   └── redteam/               # Adversarial prompt injection tests
├── backtest/                  # Backtesting harness with fees and slippage
└── ops/                       # Docker, scheduling, and alerting infrastructure
```

---

## 4. Phase Roadmap & Exit Criteria

AEGIS was engineered in strict phase sequence per PRD Section 17, advancing only when exit criteria passed with verifiable empirical evidence:

- [x] **Phase 0: Specification & Governance**
  - *Exit Criteria*: Owner reviews/signs the 5 spec files; comprehensive test matrix committed.
  - *Artifacts*: [Role Contract](docs/role-contract.md), [Authority Envelope](docs/authority-envelope.md), [Risk Policy](docs/risk-policy.md), [Strategy Spec](docs/strategy-spec.md), [Runbook](docs/runbook.md).
- [x] **Phase 1: Data and Signals**
  - *Exit Criteria*: PostgreSQL schema (14 tables, `NUMERIC` money, UTC timestamps), data ingestion, signals library passing 100% unit tests with deterministic replay.
  - *Artifacts*: `src/migrations/001_initial_schema.sql`, `src/signals/`, `tests/replay/test_deterministic_replay.py`.
- [x] **Phase 2: Backtest Harness**
  - *Exit Criteria*: Historical simulation with realistic 0.10% taker fees, 0.05% slippage, verified zero look-ahead bias, benchmark comparison.
  - *Artifacts*: `backtest/`, [Backtest Report](docs/backtest-report.md).
- [x] **Phase 3: Deterministic Risk Gate (DSoR)**
  - *Exit Criteria*: 100% pass across 8 sequential gate checks, 100 Hypothesis property runs, planted-bug tests; standalone kill switch and reconciliation verified.
  - *Artifacts*: `src/gate/`, `tests/unit/test_gate.py`, `tests/property/test_risk_invariants.py`, `tests/planted_bugs/test_gate_mutations.py`.
- [x] **Phase 4: Connector (MCP Server)**
  - *Exit Criteria*: FastMCP/MCPServer passing contract tests, verified via MCP Inspector, zero forbidden tools audited.
  - *Artifacts*: `src/connector/`, `tests/contract/test_mcp_connector.py`.
- [x] **Phase 5: Agent (Recommend Only)**
  - *Exit Criteria*: 12-turn / $1.00 bounded loop; 100% defense against prompt injection attacks; independent mathematical report recomputation verified.
  - *Artifacts*: `src/agent/loop.py`, `src/reports/recompute.py`, `tests/redteam/test_prompt_injection.py`.
- [x] **Phase 6: Paper Execution & Operations**
  - *Exit Criteria*: AutonomousScheduler, single-process file locking, alerts (80% limits, heartbeat), dashboard, 56-day (8-week) continuous paper simulation with 0 violations and 100% daily reconciliation matches.
  - *Artifacts*: `ops/scheduler.py`, `ops/alerts.py`, `ops/dashboard.py`, [Paper Execution Report](docs/paper-execution-report.md).
- [x] **Phase 7: Small Live (With Approval)**
  - *Exit Criteria*: 4-week (28-day) simulated small live run with owner approval token, slippage within 0.05% backtest assumptions, Go-Live checklist verified.
  - *Artifacts*: `docs/go-live-checklist.md`, [Live Approval Report](docs/live-approval-report.md).
- [x] **Phase 8: Full Autonomy (Target State)**
  - *Exit Criteria*: Autonomous live execution inside unchanged hard limits; demotion invariant ("any violation drops a rung") tested and verified.
  - *Artifacts*: [Full Autonomy Case & Portfolio](docs/full-autonomy-case.md), `tests/unit/test_full_autonomy.py`.
- [x] **Phase 9: Production Deployment & Operations**
  - *Exit Criteria*: Unified CLI (`aegis`), production Dockerization (`Dockerfile`, `docker-compose.yml`), `.env.example`, automated cron runner (`ops/cron.sh`).
  - *Artifacts*: `src/cli.py`, `Dockerfile`, `docker-compose.yml`, `ops/cron.sh`, `.env.example`.

---

## 5. Unified CLI & Operations

AEGIS provides a first-class command-line interface for human supervision and operational control:

```bash
# View real-time operations & risk dashboard
aegis dashboard

# Execute an autonomous trading cycle (enforcing all 6 post-flight conditions)
aegis run --mode PAPER_EXECUTION

# Verify minor-unit reconciliation between PostgreSQL state and broker
aegis reconcile

# Emergency Kill Switch (Manual halt / resume)
aegis kill --reason "Manual supervisor intervention"
aegis kill --disengage
```

---

## 6. Development Setup

### Prerequisites
- Python 3.12+
- `uv` package manager (recommended) or `pip`
- Docker & PostgreSQL 16+

```bash
# Clone the repository
git clone https://github.com/abdulhayykhan/AEGIS.git
cd AEGIS

# Create virtual environment with Python 3.12 using uv
uv venv --python 3.12
.venv\Scripts\activate   # On Windows
# source .venv/bin/activate # On Linux/macOS

# Install dependencies in editable mode with dev tools
uv pip install -e ".[dev]"

# Run tests
pytest
```
