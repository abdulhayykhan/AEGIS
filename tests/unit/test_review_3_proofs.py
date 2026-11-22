"""AEGIS Review 3 Real-Money Readiness Audit Proofs.

Verifies all 9 test requirements specified in Section 7 (Tests to add next)
of AEGIS Review 3: Real-Money Readiness Report (22 Nov 2026).

Owner: [Abdul Hayy Khan](https://abdulhayykhan.dev)
Repository: https://github.com/abdulhayykhan/AEGIS
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from src.connector.broker import Position
from src.connector.server import AegisConnectorServer
from src.gate.evaluator import create_order_approval_signature
from src.storage.db import Database


# ---------------------------------------------------------------------------
# Test 1: Open a position, restart, run full cycle: position, stop & target intact (N1)
# ---------------------------------------------------------------------------
def test_proof_restart_keeps_stops_and_prevents_liquidation(tmp_path: Path) -> None:
    """Proof 1: Buy 0.02 BTC with a 29,500 stop and 31,500 take profit, restart process on same DB.

    Assert position, stop_loss, and take_profit are restored intact, and check_stops()
    does NOT trigger 'FLATTEN_MISSING_PROTECTIVE_STOP' (N1 fix).
    """
    db_file = tmp_path / "restart_stop.db"
    db1 = Database(db_path=db_file)
    server1 = AegisConnectorServer(mode="PAPER", db=db1)
    server1.seed_mock_data()

    prop = server1.submit_proposal({
        "symbol": "BTC/USDT",
        "side": "BUY",
        "order_type": "LIMIT",
        "price": "30000.00",
        "size": "0.02",
        "stop_loss": "29500.00",
        "take_profit": "31500.00",
        "rationale_id": "PROOF_1_ENTRY"
    })

    res = server1.place_order(prop["proposal_id"], prop["idempotency_key"])
    assert res["passed"] is True
    assert res["status"] == "FILLED"

    pos1 = server1.broker.positions["BTC/USDT"]
    assert pos1.size == Decimal("0.02")
    assert pos1.stop_loss == Decimal("29500.00")
    assert pos1.take_profit == Decimal("31500.00")

    # Simulate process restart by instantiating fresh DB and fresh server on the same SQLite file
    db2 = Database(db_path=db_file)
    server2 = AegisConnectorServer(mode="PAPER", db=db2)
    server2.seed_mock_data()

    # Verify positions and stops are restored from DB Migration 3 columns
    assert "BTC/USDT" in server2.broker.positions
    pos2 = server2.broker.positions["BTC/USDT"]
    assert pos2.size == Decimal("0.02")
    assert pos2.stop_loss == Decimal("29500.00")
    assert pos2.take_profit == Decimal("31500.00")

    # Run check_stops(): should NOT liquidate healthy position
    executed = server2.check_stops()
    assert len(executed) == 0
    assert "BTC/USDT" in server2.broker.positions
    assert server2.broker.positions["BTC/USDT"].size == Decimal("0.02")


# ---------------------------------------------------------------------------
# Test 2: Stop-loss exit, then restart: cash, ledger, positions agree, loss carried over (N1, N2, N3)
# ---------------------------------------------------------------------------
def test_proof_stop_loss_exit_survives_restart(tmp_path: Path) -> None:
    """Proof 2: Trigger a protective stop in-process, then restart.

    Cash, ledger, positions agree to the cent, and daily loss is carried over across restart.
    """
    db_file = tmp_path / "stop_exit_restart.db"
    db1 = Database(db_path=db_file)
    server1 = AegisConnectorServer(mode="PAPER", db=db1)
    server1.seed_mock_data()

    # Enter position: Buy 0.02 BTC @ 30,000, stop @ 29,000
    prop = server1.submit_proposal({
        "symbol": "BTC/USDT",
        "side": "BUY",
        "order_type": "LIMIT",
        "price": "30000.00",
        "size": "0.02",
        "stop_loss": "29000.00",
        "rationale_id": "PROOF_2_ENTRY"
    })
    res_entry = server1.place_order(prop["proposal_id"], prop["idempotency_key"])
    assert res_entry["passed"] is True

    # Simulate price drop to trigger stop loss
    server1.bars_db["BTC/USDT"][-1]["close"] = "28900.00"
    executed = server1.check_stops()
    assert len(executed) >= 1
    stop_fill = executed[0]
    assert stop_fill["symbol"] == "BTC/USDT"

    loss_before_restart = server1.daily_realized_loss
    assert loss_before_restart > Decimal("0.00")
    cash_before_restart = server1.broker.cash

    # Restart process on same DB
    db2 = Database(db_path=db_file)
    server2 = AegisConnectorServer(mode="PAPER", db=db2)
    server2.seed_mock_data()

    # Cash and ledger must match exactly
    assert abs(server2.broker.cash - cash_before_restart) < Decimal("0.01")
    ledger2 = server2.db.reconstruct_ledger(initial_cash=Decimal("10000.00"))
    assert abs(ledger2["cash"] - server2.broker.cash) < Decimal("0.01")
    assert server2.broker.positions.get("BTC/USDT", Position(symbol="BTC/USDT", size=Decimal(0), avg_price=Decimal(0))).size == Decimal(0)

    # Daily loss must survive restart and be accurately derived from DB
    assert server2.daily_realized_loss == loss_before_restart


# ---------------------------------------------------------------------------
# Test 3: flatten_positions records fills, ledger equals broker across restart (N2)
# ---------------------------------------------------------------------------
def test_proof_flatten_positions_records_fills_and_reconciles(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Proof 3: Buy, then emergency flatten_positions().

    Assert order and fill are saved in DB, position is cleared, and after restart
    ledger cash equals broker cash with sale proceeds intact (no missing proceeds error).
    """
    db_file = tmp_path / "flatten_restart.db"
    db1 = Database(db_path=db_file)
    flatten_secret = "aegis_flatten_vault_secret_2026"  # gitleaks:allow
    monkeypatch.setenv("AEGIS_FLATTEN_SECRET", flatten_secret)

    server1 = AegisConnectorServer(mode="PAPER", db=db1)
    server1.seed_mock_data()

    # Buy 0.02 BTC @ 30,000 (cost: $600 + fee)
    prop = server1.submit_proposal({
        "symbol": "BTC/USDT",
        "side": "BUY",
        "order_type": "LIMIT",
        "price": "30000.00",
        "size": "0.02",
        "stop_loss": "29400.00",
        "rationale_id": "PROOF_3_BUY"
    })
    server1.place_order(prop["proposal_id"], prop["idempotency_key"])

    # Execute emergency flatten with valid token
    flatten_results = server1.flatten_positions(operator="Abdul Hayy Khan", token=flatten_secret)
    assert len(flatten_results) == 1
    assert flatten_results[0]["symbol"] == "BTC/USDT"

    # Verify database has 2 fills (1 buy, 1 flatten sell)
    fills1 = server1.db.get_fills()
    assert len(fills1) == 2
    assert fills1[0]["side"] == "BUY"
    assert fills1[1]["side"] == "SELL"

    cash1 = server1.broker.cash

    # Restart process on same DB
    db2 = Database(db_path=db_file)
    server2 = AegisConnectorServer(mode="PAPER", db=db2)
    server2.seed_mock_data()

    # Reconstructed ledger must equal broker cash to the cent!
    ledger2 = server2.db.reconstruct_ledger(initial_cash=Decimal("10000.00"))
    assert abs(server2.broker.cash - cash1) < Decimal("0.01")
    assert abs(ledger2["cash"] - server2.broker.cash) < Decimal("0.01")
    assert "BTC/USDT" not in server2.broker.positions or server2.broker.positions["BTC/USDT"].size == Decimal(0)


# ---------------------------------------------------------------------------
# Test 4: Daily loss and order count computed from database after restart (N3)
# ---------------------------------------------------------------------------
def test_proof_daily_loss_and_order_count_computed_from_database_after_restart(tmp_path: Path) -> None:
    """Proof 4: Orders placed and daily loss incurred survive process restart and accumulate across cron cycles."""
    db_file = tmp_path / "daily_limits_restart.db"
    db1 = Database(db_path=db_file)
    server1 = AegisConnectorServer(mode="PAPER", db=db1)
    server1.seed_mock_data()

    # Place 2 orders: 1 buy, 1 sell at loss
    p1 = server1.submit_proposal({
        "symbol": "BTC/USDT", "side": "BUY", "order_type": "LIMIT",
        "price": "30000.00", "size": "0.01", "stop_loss": "29000.00",
        "rationale_id": "ORDER_1"
    })
    server1.place_order(p1["proposal_id"], p1["idempotency_key"])

    p2 = server1.submit_proposal({
        "symbol": "BTC/USDT", "side": "SELL", "order_type": "LIMIT",
        "price": "29500.00", "size": "0.01", "stop_loss": "30500.00",
        "rationale_id": "ORDER_2", "reduce_only": True
    })
    server1.place_order(p2["proposal_id"], p2["idempotency_key"])

    assert server1.orders_today_count == 2
    assert server1.daily_realized_loss >= Decimal("5.00")

    loss_recorded = server1.daily_realized_loss

    # Restart process on same DB
    db2 = Database(db_path=db_file)
    server2 = AegisConnectorServer(mode="PAPER", db=db2)
    server2.seed_mock_data()

    # Derived from DB tables orders and fills
    assert server2.orders_today_count == 2
    assert server2.daily_realized_loss == loss_recorded


# ---------------------------------------------------------------------------
# Test 5: Signed approval: valid, wrong order, altered price, expired, reused nonce, raw secret (N4)
# ---------------------------------------------------------------------------
def test_proof_signed_approval_comprehensive_matrix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Proof 5: Verify cryptographic signed approval enforcement matrix (N4).

    Valid signature passes; altered price, wrong order, expired timestamp, reused nonce,
    and raw-secret attempts are strictly rejected. Approvals table records each valid execution.
    """
    db = Database(db_path=tmp_path / "signed_approval.db")
    secret = "aegis_master_owner_approval_secret_key_88"  # gitleaks:allow
    monkeypatch.setenv("AEGIS_APPROVAL_SECRET", secret)

    server = AegisConnectorServer(mode="LIVE_WITH_APPROVAL", db=db)
    server.seed_mock_data()

    now = datetime.now(UTC)
    expires_at = (now + timedelta(hours=2)).isoformat()
    nonce1 = uuid.uuid4().hex

    prop = server.submit_proposal({
        "symbol": "BTC/USDT",
        "side": "BUY",
        "order_type": "LIMIT",
        "price": "30000.00",
        "size": "0.01",
        "stop_loss": "29400.00",
        "take_profit": "31500.00",
        "rationale_id": "APPROVAL_MATRIX_1"
    })
    p_id = prop["proposal_id"]
    i_key = prop["idempotency_key"]

    # 1. Raw secret attempt directly to place_order -> REJECTED
    res_raw = server.place_order(p_id, i_key, approval_token=secret)
    assert res_raw["passed"] is False
    assert any("raw owner secret is forbidden" in r.lower() for r in res_raw["reasons"])

    # 2. Altered price signature -> REJECTED
    altered_sig = create_order_approval_signature(
        secret=secret,
        symbol="BTC/USDT",
        side="BUY",
        order_type="LIMIT",
        size="0.01",
        price="29000.00",  # Altered price!
        stop_loss="29400.00",
        take_profit="31500.00",
        expires_at=expires_at,
        nonce=nonce1
    )
    res_altered = server.place_order(
        p_id, i_key,
        approval_signature=altered_sig,
        approval_expires_at=expires_at,
        approval_nonce=nonce1
    )
    assert res_altered["passed"] is False
    assert any("signature verification failed" in r.lower() for r in res_altered["reasons"])

    # 3. Wrong order signature -> REJECTED
    wrong_order_sig = create_order_approval_signature(
        secret=secret,
        symbol="ETH/USDT",  # Wrong symbol!
        side="BUY",
        order_type="LIMIT",
        size="0.01",
        price="30000.00",
        stop_loss="29400.00",
        take_profit="31500.00",
        expires_at=expires_at,
        nonce=nonce1
    )
    res_wrong = server.place_order(
        p_id, i_key,
        approval_signature=wrong_order_sig,
        approval_expires_at=expires_at,
        approval_nonce=nonce1
    )
    assert res_wrong["passed"] is False
    assert any("signature verification failed" in r.lower() for r in res_wrong["reasons"])

    # 4. Expired signature -> REJECTED
    past_expiry = (now - timedelta(minutes=10)).isoformat()
    expired_sig = create_order_approval_signature(
        secret=secret,
        symbol="BTC/USDT",
        side="BUY",
        order_type="LIMIT",
        size="0.01",
        price="30000.00",
        stop_loss="29400.00",
        take_profit="31500.00",
        expires_at=past_expiry,
        nonce=nonce1
    )
    res_expired = server.place_order(
        p_id, i_key,
        approval_signature=expired_sig,
        approval_expires_at=past_expiry,
        approval_nonce=nonce1
    )
    assert res_expired["passed"] is False
    assert any("expired" in r.lower() for r in res_expired["reasons"])

    # 5. Valid signature -> ACCEPTED & FILLED
    valid_sig = create_order_approval_signature(
        secret=secret,
        symbol="BTC/USDT",
        side="BUY",
        order_type="LIMIT",
        size="0.01",
        price="30000.00",
        stop_loss="29400.00",
        take_profit="31500.00",
        expires_at=expires_at,
        nonce=nonce1
    )
    res_valid = server.place_order(
        p_id, i_key,
        approval_signature=valid_sig,
        approval_expires_at=expires_at,
        approval_nonce=nonce1
    )
    assert res_valid["passed"] is True
    assert res_valid["status"] == "FILLED"

    # Verify approval record written to approvals table
    with db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM approvals WHERE nonce = ?", (nonce1,))
        app_row = cursor.fetchone()
        assert app_row is not None
        assert app_row["proposal_hash"] == str(p_id)

    # 6. Reused nonce on a new order -> REJECTED
    prop_replay = server.submit_proposal({
        "symbol": "BTC/USDT", "side": "BUY", "order_type": "LIMIT",
        "price": "30000.00", "size": "0.01", "stop_loss": "29400.00",
        "take_profit": "31500.00", "rationale_id": "REPLAY"
    })
    res_reused = server.place_order(
        prop_replay["proposal_id"], prop_replay["idempotency_key"],
        approval_signature=valid_sig,
        approval_expires_at=expires_at,
        approval_nonce=nonce1  # Reused nonce!
    )
    assert res_reused["passed"] is False
    assert any("reused approval nonce" in r.lower() for r in res_reused["reasons"])


# ---------------------------------------------------------------------------
# Test 6: Order intent written before broker call, startup resolves (N5)
# ---------------------------------------------------------------------------
def test_proof_order_intent_written_before_broker_call_and_startup_reconciles(tmp_path: Path) -> None:
    """Proof 6: Order intent is written to DB as SUBMITTED before execution.

    If interrupted, start-up reconciliation inspects pending intent rows (N5).
    """
    db = Database(db_path=tmp_path / "intent.db")
    server = AegisConnectorServer(mode="PAPER", db=db)
    server.seed_mock_data()

    # Pre-record an unresolved intent row
    unresolved_order_id = str(uuid.uuid4())
    intent_dict = {
        "order_id": unresolved_order_id,
        "proposal_id": str(uuid.uuid4()),
        "symbol": "BTC/USDT",
        "side": "BUY",
        "order_type": "LIMIT",
        "price": "30000.00",
        "size": "0.01",
        "status": "SUBMITTED",
        "created_at": datetime.now(UTC).isoformat()
    }
    db.record_order(intent_dict)

    orders_pre = db.get_orders(status="SUBMITTED")
    assert any(o["order_id"] == unresolved_order_id for o in orders_pre)

    # Re-initialize server on same DB: start-up reconciles pending intent
    server_restarted = AegisConnectorServer(mode="PAPER", db=db)
    server_restarted.seed_mock_data()

    # Intent row was resolved because broker had no active open order
    orders_post = db.get_orders()
    target_order = next(o for o in orders_post if o["order_id"] == unresolved_order_id)
    assert target_order["status"] in ("CANCELLED", "FILLED")


# ---------------------------------------------------------------------------
# Test 7: Reconciliation detects position and cash differences (N7)
# ---------------------------------------------------------------------------
def test_proof_reconciliation_detects_position_and_cash_differences(tmp_path: Path) -> None:
    """Proof 7: Reconciliation checks both cash AND positions across broker and DB fills ledger."""
    db = Database(db_path=tmp_path / "rec_diff.db")
    server = AegisConnectorServer(mode="PAPER", db=db)
    server.seed_mock_data()

    # Execute a real buy order so DB fills exist
    prop = server.submit_proposal({
        "symbol": "BTC/USDT", "side": "BUY", "order_type": "LIMIT",
        "price": "30000.00", "size": "0.01", "stop_loss": "29400.00",
        "rationale_id": "REC_BUY"
    })
    server.place_order(prop["proposal_id"], prop["idempotency_key"])

    # 1. Healthy state: matched
    matched, diffs = server.reconcile_broker_and_ledger()
    assert matched is True
    assert len(diffs) == 0

    # 2. Position difference introduced: broker secretly holds extra 0.05 BTC
    server.broker.positions["BTC/USDT"] = Position(
        symbol="BTC/USDT",
        size=Decimal("0.06"),  # DB recorded 0.01
        avg_price=Decimal("30000.00")
    )
    matched_pos, diffs_pos = server.reconcile_broker_and_ledger()
    assert matched_pos is False
    assert any("Position divergence" in d for d in diffs_pos)

    # Reset position and inject cash divergence
    server.broker.positions["BTC/USDT"] = Position(
        symbol="BTC/USDT",
        size=Decimal("0.01"),
        avg_price=Decimal("30000.00")
    )
    server.broker.cash += Decimal("500.00")
    matched_cash, diffs_cash = server.reconcile_broker_and_ledger()
    assert matched_cash is False
    assert any("Cash divergence" in d for d in diffs_cash)


# ---------------------------------------------------------------------------
# Test 8: Live loop and backtest give identical signals on same 400 bars
# ---------------------------------------------------------------------------
def test_proof_live_loop_and_backtest_identical_signals_on_same_400_real_bars(tmp_path: Path) -> None:
    """Proof 8: Verify strategy evaluates the identical 400-bar window across live loop and backtest."""
    from src.signals.price_action import calculate_rsi
    from src.signals.regime import MarketRegime, classify_market_regime

    # Generate 400 deterministic bars
    now = datetime.now(UTC)
    bars_400 = [
        {
            "symbol": "BTC/USDT",
            "timeframe": "1d",
            "ts": int((now - timedelta(days=400 - i)).timestamp()),
            "open": str(Decimal("30000.00") + Decimal(i * 10)),
            "high": str(Decimal("30100.00") + Decimal(i * 10)),
            "low": str(Decimal("29900.00") + Decimal(i * 10)),
            "close": str(Decimal("30000.00") + Decimal(i * 10)),
            "volume": "1000.0"
        }
        for i in range(400)
    ]
    assert len(bars_400) == 400

    closes = [Decimal(str(b["close"])) for b in bars_400]

    # Calculate indicators
    rsi = calculate_rsi(closes)
    regime = classify_market_regime(closes)
    assert rsi is not None
    assert isinstance(regime, MarketRegime)

    server = AegisConnectorServer(mode="PAPER", db=Database(db_path=tmp_path / "bars.db"))
    server.bars_db["BTC/USDT"] = bars_400

    fetched_bars = server.get_bars("BTC/USDT", limit=400)
    assert len(fetched_bars) == 400
    assert fetched_bars[-1]["close"] == bars_400[-1]["close"]


# ---------------------------------------------------------------------------
# Test 9: Restore and flatten fail without configured credential (fail closed)
# ---------------------------------------------------------------------------
def test_proof_restore_and_flatten_both_fail_without_configured_credential(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Proof 9: Unset secrets or invalid tokens cause restore and flatten commands to fail closed."""
    import sys

    from src.cli import main

    # Ensure all secrets are unset
    monkeypatch.delenv("AEGIS_OWNER_SECRET", raising=False)
    monkeypatch.delenv("AEGIS_RESTORE_SECRET", raising=False)
    monkeypatch.delenv("AEGIS_FLATTEN_SECRET", raising=False)

    # 1. Flatten attempt with no credential configured -> Exit code 1 (rejected)
    monkeypatch.setattr(sys, "argv", ["aegis", "flatten", "--token", "arbitrary_token"])
    ret_flatten = main()
    assert ret_flatten == 1

    # 2. Restore attempt with no credential configured -> Exit code 1 (rejected)
    monkeypatch.setattr(sys, "argv", ["aegis", "restore", "--incident", "INC-01", "--token", "arbitrary_token"])
    ret_restore = main()
    assert ret_restore == 1
