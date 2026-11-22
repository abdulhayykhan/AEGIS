"""Tests verifying fixes for Review 2 Blockers and Proofs (1 to 10).

Built by [Abdul Hayy Khan](https://abdulhayykhan.dev).
"""

import hashlib
import hmac
import uuid
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ops.scheduler import AutonomousScheduler, SchedulerConfig
from ops.telegram_bot import TelegramCommandHandler
from ops.weekly_report import generate_weekly_report
from src.connector.broker import Position
from src.connector.server import AegisConnectorServer
from src.gate.kill_switch import StandaloneKillSwitch
from src.storage.db import Database


# --- PROOF 1: Restart breaks accounting (B1) ---
def test_proof_1_restart_preserves_accounting_and_reconciliation(tmp_path: Path) -> None:
    db = Database(db_path=tmp_path / "restart_test.db")
    server1 = AegisConnectorServer(mode="PAPER", db=db)
    server1.seed_mock_data()

    initial_cash = Decimal("10000.00")
    assert server1.broker.cash == initial_cash

    # Submit and execute BUY order of 0.02 BTC at 30,000 (600 USDT <= 1000 USDT max position size)
    prop_res = server1.submit_proposal({
        "symbol": "BTC/USDT",
        "side": "BUY",
        "order_type": "LIMIT",
        "price": "30000.00",
        "size": "0.02",
        "stop_loss": "29500.00",
        "take_profit": "31000.00",
        "rationale_id": "TEST_RESTART_1"
    })
    order_res = server1.place_order(
        proposal_id=prop_res["proposal_id"],
        idempotency_key=prop_res["idempotency_key"]
    )
    assert order_res["passed"] is True
    assert order_res["status"] == "FILLED"

    cash_after_fill = server1.broker.cash
    assert cash_after_fill < initial_cash
    assert "BTC/USDT" in server1.broker.positions
    assert server1.broker.positions["BTC/USDT"].size == Decimal("0.02")

    # Simulate process restart by instantiating Server 2 with same DB
    server2 = AegisConnectorServer(mode="PAPER", db=db)
    server2.seed_mock_data()

    # Invariant: Server 2 must reconstruct cash, positions, trade history, fees, and idempotency
    assert server2.broker.cash == cash_after_fill, "B1 Fix: Cash must be reconstructed from ledger, not reset to 10k"
    assert "BTC/USDT" in server2.broker.positions
    assert server2.broker.positions["BTC/USDT"].size == Decimal("0.02")
    assert len(server2.broker.trade_history) >= 1
    assert server2.broker.total_fees_paid > Decimal(0)
    assert uuid.UUID(prop_res["proposal_id"]) in server2.executed_proposal_ids

    # Double-fill attempt on restored server must be rejected
    dup_res = server2.place_order(
        proposal_id=prop_res["proposal_id"],
        idempotency_key=prop_res["idempotency_key"]
    )
    assert dup_res["passed"] is False
    assert "already been executed" in dup_res["reasons"][0]


# --- PROOF 2: Demotion persistence and Audit Trail (B7 & B8) ---
def test_proof_2_audit_trail_and_demotion_persistence(tmp_path: Path) -> None:
    db = Database(db_path=tmp_path / "audit_test.db")
    server = AegisConnectorServer(mode="PAPER", db=db)
    server.seed_mock_data()

    sched_config = SchedulerConfig(lock_file=tmp_path / "sched.lock")
    scheduler = AutonomousScheduler(connector=server, scheduler_config=sched_config)
    report = scheduler.run_scheduled_cycle()
    assert report.success is True

    # B7: Database MUST contain runs, equity snapshots, and gate records
    runs = db.get_runs()
    assert len(runs) >= 1, "B7 Fix: Scheduled runs must be recorded in database"
    assert runs[0]["status"] == "SUCCESS"

    latest_snap = db.get_latest_equity_snapshot()
    assert latest_snap is not None, "B7 Fix: Equity snapshot must be recorded in database"
    assert Decimal(str(latest_snap["equity"])) > Decimal(0)

    # Test demotion recording on safety violation
    db.record_demotion("INC-TEST-01", "RECOMMEND_ONLY", "Test safety violation")
    assert db.get_active_demotion_rung() == "RECOMMEND_ONLY"

    # Test demotion resolution
    db.resolve_demotion("INC-TEST-01", "Abdul Hayy Khan")
    assert db.get_active_demotion_rung() is None


# --- PROOF 3: Legitimate exits during ATR spike (B6) ---
def test_proof_3_legitimate_exit_allowed_during_volatility_spike(tmp_path: Path) -> None:
    db = Database(db_path=tmp_path / "exit_test.db")
    server = AegisConnectorServer(mode="PAPER", db=db)
    server.seed_mock_data()

    # Pre-seed an open position of 0.1 BTC at 30,000
    server.broker.positions["BTC/USDT"] = Position(
        symbol="BTC/USDT",
        size=Decimal("0.1"),
        avg_price=Decimal("30000.00"),
        stop_loss=Decimal("29000.00")
    )

    # Submit a reduce-only SELL exit with a huge ATR stop distance ($5,000)
    # Under old logic, 5000 * 0.1 = $500 risk, which breached the 1% risk limit ($100)
    exit_prop = server.submit_proposal({
        "symbol": "BTC/USDT",
        "side": "SELL",
        "order_type": "LIMIT",
        "price": "30000.00",
        "size": "0.1",
        "stop_loss": "35000.00",  # 5,000 above price
        "take_profit": "28000.00",
        "rationale_id": "EXIT_SPIKE_TEST",
        "reduce_only": True
    })

    order_res = server.place_order(
        proposal_id=exit_prop["proposal_id"],
        idempotency_key=exit_prop["idempotency_key"]
    )
    assert order_res["passed"] is True, f"B6 Fix: Reduce-only exit must not be blocked by per-trade risk sizing: {order_res.get('reasons')}"
    assert order_res["status"] == "FILLED"


# --- PROOF 4: Missing data fails closed (B4) ---
def test_proof_4_missing_market_data_fails_closed(tmp_path: Path) -> None:
    db = Database(db_path=tmp_path / "missing_data.db")
    server = AegisConnectorServer(mode="PAPER", db=db)
    # Notice: do NOT seed mock data! bars_db is empty

    prop = server.submit_proposal({
        "symbol": "BTC/USDT",
        "side": "BUY",
        "order_type": "LIMIT",
        "price": "30000.00",
        "size": "0.01",
        "stop_loss": "29000.00",
        "rationale_id": "TEST_MISSING_DATA"
    })

    res = server.place_order(
        proposal_id=prop["proposal_id"],
        idempotency_key=prop["idempotency_key"]
    )
    assert res["passed"] is False
    assert any("Missing market data" in r or "stale" in r.lower() for r in res["reasons"]), "B4 Fix: Must fail closed when market data is missing"


# --- PROOF 5: Approval secrets and signatures (B3) ---
def test_proof_5_approval_forgery_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = Database(db_path=tmp_path / "approval_sec.db")
    server = AegisConnectorServer(mode="LIVE_WITH_APPROVAL", db=db)
    server.seed_mock_data()

    # 1. Unset secret -> Must fail closed even if token is passed
    monkeypatch.delenv("AEGIS_OWNER_SECRET", raising=False)
    monkeypatch.delenv("AEGIS_OWNER_TOKEN", raising=False)

    prop = server.submit_proposal({
        "symbol": "BTC/USDT",
        "side": "BUY",
        "order_type": "LIMIT",
        "price": "30000.00",
        "size": "0.001",
        "stop_loss": "29000.00",
        "rationale_id": "TEST_APP_1"
    })

    # Forgery attempt using old static token
    res_forgery = server.place_order(
        proposal_id=prop["proposal_id"],
        idempotency_key=prop["idempotency_key"],
        approval_token="OWNER_ABDUL_HAYY_SIGNATURE"
    )
    assert res_forgery["passed"] is False, "B3 Fix: Static token bypass must be rejected"
    assert any("not configured" in r or "invalid" in r.lower() for r in res_forgery["reasons"])

    # 2. Configure secret and sign canonically
    secret = "aegis_mock_owner_vault_2026"  # gitleaks:allow
    monkeypatch.setenv("AEGIS_OWNER_SECRET", secret)

    # Wrong secret token -> Reject
    res_wrong = server.place_order(
        proposal_id=prop["proposal_id"],
        idempotency_key=prop["idempotency_key"],
        approval_token="wrong_secret_token"
    )
    assert res_wrong["passed"] is False

    # Valid secret token -> Accept
    res_valid_token = server.place_order(
        proposal_id=prop["proposal_id"],
        idempotency_key=prop["idempotency_key"],
        approval_token=secret
    )
    assert res_valid_token["passed"] is True

    # 3. Cryptographic HMAC signature over canonical proposal hash
    prop2 = server.submit_proposal({
        "symbol": "BTC/USDT",
        "side": "BUY",
        "order_type": "LIMIT",
        "price": "30000.00",
        "size": "0.001",
        "stop_loss": "29000.00",
        "rationale_id": "TEST_APP_2"
    })
    p2_id = prop2["proposal_id"]
    canonical_msg = f"{p2_id}:BTC/USDT:BUY:0.001:30000.00:29000.00"
    valid_sig = hmac.new(secret.encode(), canonical_msg.encode(), hashlib.sha256).hexdigest()

    res_valid_sig = server.place_order(
        proposal_id=p2_id,
        idempotency_key=prop2["idempotency_key"],
        approval_signature=valid_sig
    )
    assert res_valid_sig["passed"] is True, f"B3 Fix: Valid HMAC signature must pass: {res_valid_sig.get('reasons')}"


# --- PROOF 8: Kill switch and Telegram authorization fail closed (B4) ---
def test_proof_8_kill_switch_and_telegram_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # 1. Kill Switch disengage requires secret
    lock_path = tmp_path / "test_ks.lock"
    ks = StandaloneKillSwitch(lock_file_path=lock_path)
    ks.engage(reason="Test Emergency")
    assert ks.is_engaged() is True

    # When secret is unset -> Cannot disengage
    monkeypatch.delenv("AEGIS_OWNER_SECRET", raising=False)
    monkeypatch.delenv("AEGIS_OWNER_TOKEN", raising=False)
    with pytest.raises(PermissionError, match="not configured"):
        ks.disengage(operator="Abdul Hayy Khan")

    # When secret is set but token is wrong -> Cannot disengage
    monkeypatch.setenv("AEGIS_OWNER_SECRET", "super_secret_operator_key")
    with pytest.raises(PermissionError, match="Invalid owner security token"):
        ks.disengage(operator="Abdul Hayy Khan", token="wrong_token")

    # With valid token -> Disengages cleanly
    ks.disengage(operator="Abdul Hayy Khan", token="super_secret_operator_key")
    assert ks.is_engaged() is False

    # 2. Telegram command handler requires authorized_chat_id
    server = AegisConnectorServer(mode="PAPER")
    handler_unauth = TelegramCommandHandler(server=server, authorized_chat_id="")
    resp = handler_unauth.handle_command(user_chat_id="123456", command_text="/status")
    assert "Unauthorized" in resp, "B4 Fix: Telegram handler must fail closed when chat ID is unset"


# --- PROOF 9: Stop Loss and Take Profit enforcement (B5) ---
def test_proof_9_stop_loss_and_take_profit_enforcement(tmp_path: Path) -> None:
    db = Database(db_path=tmp_path / "stops_test.db")
    server = AegisConnectorServer(mode="PAPER", db=db)
    server.seed_mock_data()

    # Buy 0.02 BTC at 30,000 with stop loss at 29,000 and take profit at 32,000
    prop = server.submit_proposal({
        "symbol": "BTC/USDT",
        "side": "BUY",
        "order_type": "LIMIT",
        "price": "30000.00",
        "size": "0.02",
        "stop_loss": "29000.00",
        "take_profit": "32000.00",
        "rationale_id": "TEST_PROTECTIVE_STOP"
    })
    order_res = server.place_order(proposal_id=prop["proposal_id"], idempotency_key=prop["idempotency_key"])
    assert order_res["passed"] is True
    assert "BTC/USDT" in server.broker.positions
    assert server.broker.positions["BTC/USDT"].stop_loss == Decimal("29000.00")

    # Price drops to 28,500 (breaching stop loss of 29,000)
    executed_stops = server.check_stops()
    # Or call broker check_protective_stops directly with mark price
    executed_stops = server.broker.check_protective_stops({"BTC/USDT": Decimal("28500.00")})
    assert len(executed_stops) == 1, "B5 Fix: Stop loss must trigger immediate protective exit fill"
    assert executed_stops[0]["trigger"] == "STOP_LOSS"
    assert "BTC/USDT" not in server.broker.positions, "B5 Fix: Position must be closed upon stop breach"


# --- PROOF 10: Audit write failure hard stop (B7) ---
def test_proof_10_audit_write_failure_hard_stops_order(tmp_path: Path) -> None:
    db = Database(db_path=tmp_path / "audit_fail.db")
    server = AegisConnectorServer(mode="PAPER", db=db)
    server.seed_mock_data()

    prop = server.submit_proposal({
        "symbol": "BTC/USDT",
        "side": "BUY",
        "order_type": "LIMIT",
        "price": "30000.00",
        "size": "0.01",
        "stop_loss": "29500.00",
        "rationale_id": "TEST_AUDIT_FAIL"
    })

    initial_cash = server.broker.cash

    # Mock DB record_gate_decision to raise an error
    server.db.record_gate_decision = MagicMock(side_effect=RuntimeError("Disk I/O error on audit log"))  # type: ignore[method-assign]

    res = server.place_order(
        proposal_id=prop["proposal_id"],
        idempotency_key=prop["idempotency_key"]
    )
    assert res["passed"] is False
    assert res["status"] == "ERROR"
    assert "audit write failed" in res["reasons"][0].lower()
    assert server.broker.cash == initial_cash, "B7 Fix: Order must not execute when audit write fails"
    assert "BTC/USDT" not in server.broker.positions


# --- Weekly Report Multi-Asset Pairing Test ---
def test_weekly_report_groups_by_symbol_correctly(tmp_path: Path) -> None:
    db = Database(db_path=tmp_path / "weekly_multi.db")

    # Insert BTC Buy at 30,000 and BTC Sell at 31,000 -> +$100 profit (size 0.1)
    db.record_fill({
        "order_id": str(uuid.uuid4()),
        "symbol": "BTC/USDT",
        "side": "BUY",
        "price": "30000.00",
        "size": "0.1",
        "fee": "3.00",
        "filled_at": "2026-11-20T10:00:00Z"
    })
    db.record_fill({
        "order_id": str(uuid.uuid4()),
        "symbol": "BTC/USDT",
        "side": "SELL",
        "price": "31000.00",
        "size": "0.1",
        "fee": "3.10",
        "filled_at": "2026-11-21T10:00:00Z"
    })

    # Insert ETH Buy at 2,000 and ETH Sell at 1,900 -> -$10 loss (size 0.1)
    db.record_fill({
        "order_id": str(uuid.uuid4()),
        "symbol": "ETH/USDT",
        "side": "BUY",
        "price": "2000.00",
        "size": "0.1",
        "fee": "0.20",
        "filled_at": "2026-11-20T11:00:00Z"
    })
    db.record_fill({
        "order_id": str(uuid.uuid4()),
        "symbol": "ETH/USDT",
        "side": "SELL",
        "price": "1900.00",
        "size": "0.1",
        "fee": "0.19",
        "filled_at": "2026-11-21T11:00:00Z"
    })

    report = generate_weekly_report(db=db)
    assert report.total_trades == 4
    assert report.winning_trades == 1
    assert report.losing_trades == 1
    assert report.gross_profit == Decimal("100.00")
    assert report.gross_loss == Decimal("10.00")
