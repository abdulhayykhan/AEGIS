import json
import os
import sqlite3
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

DEFAULT_DB_PATH = Path("data/aegis.db")


class Database:
    """Persistent storage engine supporting SQLite and PostgreSQL compatibility.
    
    Ensures state (positions, orders, fills, runs, gate decisions, demotions)
    survives across processes and cron runs per PRD Section 6 & 8.
    """

    def __init__(self, db_path: Path | str | None = None) -> None:
        if db_path is None:
            env_path = os.getenv("AEGIS_DB_PATH")
            self.db_path = Path(env_path) if env_path else DEFAULT_DB_PATH
        else:
            self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def clear_all(self) -> None:
        """Clear all records from dynamic tables (useful for test isolation and resets)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM event_ledger")
            cursor.execute("DELETE FROM demotions")
            cursor.execute("DELETE FROM equity_snapshots")
            cursor.execute("DELETE FROM positions")
            cursor.execute("DELETE FROM fills")
            cursor.execute("DELETE FROM orders")
            cursor.execute("DELETE FROM gate_decisions")
            cursor.execute("DELETE FROM proposals")
            cursor.execute("DELETE FROM runs")
            conn.commit()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Migration tracking table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL,
                    description TEXT NOT NULL
                )
            """)

            # Runs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    mode TEXT NOT NULL DEFAULT 'PAPER',
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    status TEXT NOT NULL,
                    turns_executed INTEGER NOT NULL DEFAULT 1,
                    cost_usd TEXT NOT NULL DEFAULT '0.00',
                    stop_reason TEXT,
                    summary TEXT
                )
            """)
            cursor.execute("PRAGMA table_info(runs)")
            run_cols = {row["name"] for row in cursor.fetchall()}
            if run_cols and "mode" not in run_cols:
                cursor.execute("ALTER TABLE runs ADD COLUMN mode TEXT NOT NULL DEFAULT 'PAPER'")

            # Proposals table with UNIQUE constraint on idempotency_key
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS proposals (
                    proposal_id TEXT PRIMARY KEY,
                    idempotency_key TEXT UNIQUE NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    order_type TEXT NOT NULL,
                    price TEXT NOT NULL,
                    size TEXT NOT NULL,
                    stop_loss TEXT NOT NULL,
                    take_profit TEXT,
                    rationale_id TEXT,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            cursor.execute("PRAGMA table_info(proposals)")
            prop_cols = {row["name"] for row in cursor.fetchall()}
            if prop_cols and "reduce_only" not in prop_cols:
                cursor.execute("ALTER TABLE proposals ADD COLUMN reduce_only INTEGER NOT NULL DEFAULT 0")

            # Gate decisions audit log
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS gate_decisions (
                    decision_id TEXT PRIMARY KEY,
                    proposal_id TEXT NOT NULL,
                    passed INTEGER NOT NULL,
                    checks_json TEXT NOT NULL,
                    reasons_json TEXT NOT NULL,
                    decided_at TEXT NOT NULL
                )
            """)

            # Orders table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    order_id TEXT PRIMARY KEY,
                    proposal_id TEXT,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    order_type TEXT NOT NULL,
                    price TEXT NOT NULL,
                    size TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)

            # Fills ledger
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS fills (
                    fill_id TEXT PRIMARY KEY,
                    order_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    price TEXT NOT NULL,
                    size TEXT NOT NULL,
                    fee TEXT NOT NULL,
                    filled_at TEXT NOT NULL
                )
            """)

            # Open positions
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS positions (
                    symbol TEXT PRIMARY KEY,
                    size TEXT NOT NULL,
                    avg_entry_price TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # Equity snapshots
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS equity_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    ts TEXT NOT NULL,
                    equity TEXT NOT NULL,
                    cash TEXT NOT NULL,
                    daily_realized_loss TEXT NOT NULL
                )
            """)

            # Demotions & Autonomy governance
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS demotions (
                    incident_id TEXT PRIMARY KEY,
                    current_rung TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    resolved INTEGER NOT NULL,
                    resolved_by TEXT,
                    resolved_at TEXT
                )
            """)

            # Append-only Event Ledger (PRD Section 6 & Review Section 6)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS event_ledger (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    aggregate_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)

            # Reconciliations table (PRD Section 8 & Review Finding C5)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reconciliations (
                    reconciliation_id TEXT PRIMARY KEY,
                    ts TEXT NOT NULL,
                    matched INTEGER NOT NULL,
                    diffs_json TEXT NOT NULL
                )
            """)

            # Single-use Owner Approvals table (Review Finding B3)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS approvals (
                    approval_id TEXT PRIMARY KEY,
                    proposal_hash TEXT NOT NULL,
                    signer TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    nonce TEXT UNIQUE NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)

            # Seed migration record
            cursor.execute("""
                INSERT OR IGNORE INTO schema_migrations (version, applied_at, description)
                VALUES (1, ?, 'Initial AEGIS persistent schema with migration tracking')
            """, (datetime.now(UTC).isoformat(),))
            cursor.execute("""
                INSERT OR IGNORE INTO schema_migrations (version, applied_at, description)
                VALUES (2, ?, 'Add reconciliations and approvals audit tables')
            """, (datetime.now(UTC).isoformat(),))
            conn.commit()

    def get_applied_migrations(self) -> list[dict[str, Any]]:
        """Return list of all applied schema migrations."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT version, applied_at, description FROM schema_migrations ORDER BY version ASC")
            return [dict(row) for row in cursor.fetchall()]

    # --- Append-only Event Ledger operations ---
    def record_event(self, event_type: str, aggregate_id: str, payload: dict[str, Any]) -> str:
        """Record an immutable event into the audit event ledger."""
        event_id = str(uuid.uuid4())
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO event_ledger (event_id, event_type, aggregate_id, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                event_id,
                event_type,
                aggregate_id,
                json.dumps(payload, default=str),
                datetime.now(UTC).isoformat()
            ))
            conn.commit()
        return event_id

    def get_events(self, event_type: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if event_type:
                cursor.execute("""
                    SELECT event_id, event_type, aggregate_id, payload_json, created_at
                    FROM event_ledger WHERE event_type = ? ORDER BY created_at ASC LIMIT ?
                """, (event_type, limit))
            else:
                cursor.execute("""
                    SELECT event_id, event_type, aggregate_id, payload_json, created_at
                    FROM event_ledger ORDER BY created_at ASC LIMIT ?
                """, (limit,))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def replay_events(self, aggregate_id: str | None = None) -> list[dict[str, Any]]:
        """Replay events from beginning of stream to reconstruct deterministic state."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if aggregate_id:
                cursor.execute("""
                    SELECT event_id, event_type, aggregate_id, payload_json, created_at
                    FROM event_ledger WHERE aggregate_id = ? ORDER BY created_at ASC
                """, (aggregate_id,))
            else:
                cursor.execute("""
                    SELECT event_id, event_type, aggregate_id, payload_json, created_at
                    FROM event_ledger ORDER BY created_at ASC
                """)
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    # --- Run tracking operations ---
    def record_run_start(self, run_id: str, mode: str = "PAPER") -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO runs (run_id, mode, started_at, status, turns_executed, cost_usd)
                VALUES (?, ?, ?, 'RUNNING', 0, '0.00')
            """, (run_id, mode, datetime.now(UTC).isoformat()))
            conn.commit()

    def record_run_complete(
        self,
        run_id: str,
        status: str = "SUCCESS",
        turns_executed: int = 1,
        cost_usd: Decimal = Decimal("0.01"),
        stop_reason: str = "NORMAL_COMPLETION",
        summary: str = ""
    ) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE runs
                SET completed_at = ?, status = ?, turns_executed = ?, cost_usd = ?, stop_reason = ?, summary = ?
                WHERE run_id = ?
            """, (
                datetime.now(UTC).isoformat(),
                status,
                turns_executed,
                str(cost_usd),
                stop_reason,
                summary,
                run_id
            ))
            conn.commit()

    def record_run(
        self,
        run_id: str,
        mode: str,
        status: str = "SUCCESS",
        started_at: str | None = None,
        completed_at: str | None = None,
        turns_executed: int = 1,
        cost_usd: Decimal = Decimal("0.01"),
        proposals_count: int = 0,
        orders_count: int = 0,
        error_message: str = "",
        details_json: str = "{}"
    ) -> None:
        start = started_at or datetime.now(UTC).isoformat()
        comp = completed_at or datetime.now(UTC).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO runs (
                    run_id, mode, started_at, completed_at, status, turns_executed, cost_usd, summary
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (run_id, mode, start, comp, status, turns_executed, str(cost_usd), error_message))
            conn.commit()

    # --- Proposal operations ---
    def store_proposal(self, proposal_dict: dict[str, Any]) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO proposals (
                    proposal_id, idempotency_key, symbol, side, order_type,
                    price, size, stop_loss, take_profit, rationale_id, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(proposal_dict["proposal_id"]),
                str(proposal_dict["idempotency_key"]),
                str(proposal_dict["symbol"]),
                str(proposal_dict["side"]),
                str(proposal_dict["order_type"]),
                str(proposal_dict["price"]),
                str(proposal_dict["size"]),
                str(proposal_dict["stop_loss"]),
                str(proposal_dict.get("take_profit", "")),
                str(proposal_dict.get("rationale_id", "")),
                "STORED",
                datetime.now(UTC).isoformat()
            ))
            conn.commit()

    def mark_proposal_executed(self, proposal_id: str | uuid.UUID) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE proposals SET status = 'EXECUTED' WHERE proposal_id = ?
            """, (str(proposal_id),))
            conn.commit()

    def is_proposal_executed(self, proposal_id: str | uuid.UUID) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT status FROM proposals WHERE proposal_id = ?
            """, (str(proposal_id),))
            row = cursor.fetchone()
            return bool(row and row["status"] == "EXECUTED")

    def get_proposals(self) -> list[dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM proposals ORDER BY created_at ASC")
            return [dict(r) for r in cursor.fetchall()]

    # --- Gate Decisions audit logging (Finding B7) ---
    def record_gate_decision(self, decision_dict: dict[str, Any]) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO gate_decisions (
                    decision_id, proposal_id, passed, checks_json, reasons_json, decided_at
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                str(decision_dict.get("decision_id", uuid.uuid4())),
                str(decision_dict["proposal_id"]),
                1 if decision_dict["passed"] else 0,
                json.dumps(decision_dict.get("checks", {}), default=str),
                json.dumps(decision_dict.get("reasons", []), default=str),
                str(decision_dict.get("decided_at", datetime.now(UTC).isoformat()))
            ))
            conn.commit()

    def get_gate_decisions(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM gate_decisions ORDER BY decided_at DESC LIMIT ?", (limit,))
            return [dict(r) for r in cursor.fetchall()]

    # --- Equity Snapshots (Finding B1 & B7) ---
    def record_equity_snapshot(
        self,
        equity: Decimal,
        cash: Decimal,
        daily_realized_loss: Decimal,
        snapshot_id: str | None = None
    ) -> str:
        s_id = snapshot_id or str(uuid.uuid4())
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO equity_snapshots (snapshot_id, ts, equity, cash, daily_realized_loss)
                VALUES (?, ?, ?, ?, ?)
            """, (
                s_id,
                datetime.now(UTC).isoformat(),
                str(equity),
                str(cash),
                str(daily_realized_loss)
            ))
            conn.commit()
        return s_id

    def get_latest_equity_snapshot(self) -> dict[str, Any] | None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM equity_snapshots ORDER BY ts DESC LIMIT 1")
            row = cursor.fetchone()
            if not row:
                return None
            return {
                "snapshot_id": row["snapshot_id"],
                "ts": row["ts"],
                "equity": Decimal(row["equity"]),
                "cash": Decimal(row["cash"]),
                "daily_realized_loss": Decimal(row["daily_realized_loss"])
            }

    def get_max_equity(self, default: Decimal = Decimal("10000.00")) -> Decimal:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT equity FROM equity_snapshots")
            rows = cursor.fetchall()
            if not rows:
                return default
            return max(Decimal(r["equity"]) for r in rows)

    # --- Reconciliations & Approvals ---
    def record_reconciliation(self, matched: bool, diffs: list[str]) -> str:
        r_id = str(uuid.uuid4())
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO reconciliations (reconciliation_id, ts, matched, diffs_json)
                VALUES (?, ?, ?, ?)
            """, (r_id, datetime.now(UTC).isoformat(), 1 if matched else 0, json.dumps(diffs)))
            conn.commit()
        return r_id

    def get_reconciliations(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM reconciliations ORDER BY ts DESC LIMIT ?", (limit,))
            return [dict(r) for r in cursor.fetchall()]

    def record_approval(self, proposal_hash: str, signer: str, expires_at: str, nonce: str) -> str:
        app_id = str(uuid.uuid4())
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO approvals (approval_id, proposal_hash, signer, expires_at, nonce, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (app_id, proposal_hash, signer, expires_at, nonce, datetime.now(UTC).isoformat()))
            conn.commit()
        return app_id

    def is_approval_nonce_used(self, nonce: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT approval_id FROM approvals WHERE nonce = ?", (nonce,))
            return cursor.fetchone() is not None

    def get_runs(self, mode: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if mode:
                cursor.execute("SELECT * FROM runs WHERE mode = ? ORDER BY started_at DESC LIMIT ?", (mode, limit))
            else:
                cursor.execute("SELECT * FROM runs ORDER BY started_at DESC LIMIT ?", (limit,))
            return [dict(r) for r in cursor.fetchall()]

    def count_distinct_run_days(self, mode: str | None = None) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if mode:
                cursor.execute("""
                    SELECT COUNT(DISTINCT substr(started_at, 1, 10)) as days
                    FROM runs WHERE mode = ? AND status = 'SUCCESS'
                """, (mode,))
            else:
                cursor.execute("""
                    SELECT COUNT(DISTINCT substr(started_at, 1, 10)) as days
                    FROM runs WHERE status = 'SUCCESS'
                """)
            row = cursor.fetchone()
            return int(row["days"]) if row else 0

    def get_orders(self, status: str | None = None) -> list[dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if status:
                cursor.execute("SELECT * FROM orders WHERE status = ? ORDER BY created_at ASC", (status,))
            else:
                cursor.execute("SELECT * FROM orders ORDER BY created_at ASC")
            return [dict(r) for r in cursor.fetchall()]

    def get_fills(self, symbol: str | None = None) -> list[dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if symbol:
                cursor.execute("SELECT * FROM fills WHERE symbol = ? ORDER BY filled_at ASC", (symbol,))
            else:
                cursor.execute("SELECT * FROM fills ORDER BY filled_at ASC")
            return [dict(r) for r in cursor.fetchall()]

    def atomic_execute_order_and_fill(
        self,
        order_dict: dict[str, Any],
        fill_dict: dict[str, Any] | None = None,
        position_update: tuple[str, Decimal, Decimal] | None = None,
        snapshot_dict: dict[str, Any] | None = None,
        event_dict: dict[str, Any] | None = None
    ) -> None:
        """Execute order, fill, position, snapshot, and event ledger updates in a single atomic transaction."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # 1. Save Order
            cursor.execute("""
                INSERT OR REPLACE INTO orders (
                    order_id, proposal_id, symbol, side, order_type, price, size, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(order_dict["order_id"]),
                str(order_dict.get("proposal_id", "")),
                str(order_dict["symbol"]),
                str(order_dict["side"]),
                str(order_dict["order_type"]),
                str(order_dict["price"]),
                str(order_dict["size"]),
                str(order_dict["status"]),
                str(order_dict["created_at"])
            ))

            # 2. Record Fill if provided (only for filled orders)
            if fill_dict:
                cursor.execute("""
                    INSERT INTO fills (
                        fill_id, order_id, symbol, side, price, size, fee, filled_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(fill_dict.get("fill_id", uuid.uuid4())),
                    str(fill_dict["order_id"]),
                    str(fill_dict["symbol"]),
                    str(fill_dict["side"]),
                    str(fill_dict["price"]),
                    str(fill_dict["size"]),
                    str(fill_dict.get("fee", "0.00")),
                    str(fill_dict.get("filled_at", datetime.now(UTC).isoformat()))
                ))

            # 3. Update Position if provided
            if position_update:
                sym, size, avg_p = position_update
                if size <= Decimal(0):
                    cursor.execute("DELETE FROM positions WHERE symbol = ?", (sym,))
                else:
                    cursor.execute("""
                        INSERT OR REPLACE INTO positions (symbol, size, avg_entry_price, updated_at)
                        VALUES (?, ?, ?, ?)
                    """, (sym, str(size), str(avg_p), datetime.now(UTC).isoformat()))

            # 4. Record Snapshot if provided
            if snapshot_dict:
                cursor.execute("""
                    INSERT INTO equity_snapshots (snapshot_id, ts, equity, cash, daily_realized_loss)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    str(snapshot_dict.get("snapshot_id", uuid.uuid4())),
                    str(snapshot_dict.get("ts", datetime.now(UTC).isoformat())),
                    str(snapshot_dict["equity"]),
                    str(snapshot_dict["cash"]),
                    str(snapshot_dict["daily_realized_loss"])
                ))

            # 5. Record Event if provided
            if event_dict:
                cursor.execute("""
                    INSERT INTO event_ledger (event_id, event_type, aggregate_id, payload_json, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    str(event_dict.get("event_id", uuid.uuid4())),
                    str(event_dict["event_type"]),
                    str(event_dict["aggregate_id"]),
                    json.dumps(event_dict.get("payload", {}), default=str),
                    str(event_dict.get("created_at", datetime.now(UTC).isoformat()))
                ))

            # 6. Mark proposal executed
            if order_dict.get("proposal_id"):
                cursor.execute("""
                    UPDATE proposals SET status = 'EXECUTED' WHERE proposal_id = ?
                """, (str(order_dict["proposal_id"]),))

            conn.commit()

    # --- Position & Order operations ---
    def save_order(self, order_dict: dict[str, Any]) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO orders (
                    order_id, proposal_id, symbol, side, order_type, price, size, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(order_dict["order_id"]),
                str(order_dict.get("proposal_id", "")),
                str(order_dict["symbol"]),
                str(order_dict["side"]),
                str(order_dict["order_type"]),
                str(order_dict["price"]),
                str(order_dict["size"]),
                str(order_dict["status"]),
                str(order_dict["created_at"])
            ))
            conn.commit()

    def record_fill(self, fill_dict: dict[str, Any]) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO fills (
                    fill_id, order_id, symbol, side, price, size, fee, filled_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(fill_dict.get("fill_id", uuid.uuid4())),
                str(fill_dict["order_id"]),
                str(fill_dict["symbol"]),
                str(fill_dict["side"]),
                str(fill_dict["price"]),
                str(fill_dict["size"]),
                str(fill_dict.get("fee", "0.00")),
                str(fill_dict.get("filled_at", datetime.now(UTC).isoformat()))
            ))
            conn.commit()

    def get_positions(self) -> dict[str, dict[str, Decimal]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT symbol, size, avg_entry_price FROM positions")
            rows = cursor.fetchall()
            return {
                r["symbol"]: {
                    "size": Decimal(r["size"]),
                    "avg_price": Decimal(r["avg_entry_price"])
                }
                for r in rows
            }

    def update_position(self, symbol: str, size: Decimal, avg_price: Decimal) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if size <= Decimal(0):
                cursor.execute("DELETE FROM positions WHERE symbol = ?", (symbol,))
            else:
                cursor.execute("""
                    INSERT OR REPLACE INTO positions (symbol, size, avg_entry_price, updated_at)
                    VALUES (?, ?, ?, ?)
                """, (symbol, str(size), str(avg_price), datetime.now(UTC).isoformat()))
            conn.commit()

    # --- Autonomy Demotion Persistence (H6) ---
    def record_demotion(self, incident_id: str, current_rung: str, reason: str) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO demotions (
                    incident_id, current_rung, reason, occurred_at, resolved
                ) VALUES (?, ?, ?, ?, 0)
            """, (incident_id, current_rung, reason, datetime.now(UTC).isoformat()))
            conn.commit()

    def get_active_demotion_rung(self) -> str | None:
        """Return the lowest active demoted rung, if any unresolved incidents exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT current_rung FROM demotions WHERE resolved = 0 ORDER BY occurred_at DESC LIMIT 1
            """)
            row = cursor.fetchone()
            return str(row["current_rung"]) if row else None

    def resolve_demotion(self, incident_id: str, operator: str) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE demotions SET resolved = 1, resolved_by = ?, resolved_at = ?
                WHERE incident_id = ?
            """, (operator, datetime.now(UTC).isoformat(), incident_id))
            conn.commit()

    # --- Reconciliation Ledger Rebuild (C5) ---
    def reconstruct_ledger(self, initial_cash: Decimal = Decimal("10000.00")) -> dict[str, Any]:
        """Reconstruct cash, equity, and positions from immutable fills table."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT symbol, side, price, size, fee FROM fills ORDER BY filled_at ASC")
            fills = cursor.fetchall()

        cash = initial_cash
        positions: dict[str, dict[str, Decimal]] = {}

        for f in fills:
            price = Decimal(f["price"])
            size = Decimal(f["size"])
            fee = Decimal(f["fee"])
            cost = price * size
            sym = f["symbol"]

            if f["side"] == "BUY":
                cash -= (cost + fee)
                if sym in positions:
                    cur_size = positions[sym]["size"]
                    cur_avg = positions[sym]["avg_price"]
                    new_size = cur_size + size
                    new_avg = ((cur_avg * cur_size) + cost) / new_size
                    positions[sym] = {"size": new_size, "avg_price": new_avg}
                else:
                    positions[sym] = {"size": size, "avg_price": price}
            elif f["side"] == "SELL":
                cash += (cost - fee)
                if sym in positions:
                    rem_size = positions[sym]["size"] - size
                    if rem_size <= Decimal(0):
                        del positions[sym]
                    else:
                        positions[sym]["size"] = rem_size

        return {
            "cash": cash,
            "positions": positions
        }
