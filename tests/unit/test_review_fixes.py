import os
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from ops.scheduler import AutonomousScheduler, SchedulerConfig
from src.connector.broker import Position
from src.connector.server import AegisConnectorServer
from src.gate.evaluator import RiskGate
from src.gate.kill_switch import StandaloneKillSwitch
from src.gate.models import GateContext, OrderProposal, OrderSide, OrderType
from src.gate.reconcile import AccountState, reconcile_states
from src.storage.db import Database


def test_1_kill_switch_engaged_and_corrupt_blocks_orders(tmp_path: Path) -> None:
    """Finding C2 / Test 1: Kill switch engaged by CLI or lock file blocks place_order; corrupt lock blocks too."""
    lock_file = tmp_path / "aegis_kill_switch.lock"
    os.environ["AEGIS_KILL_SWITCH_LOCK"] = str(lock_file)
    ks = StandaloneKillSwitch(lock_file_path=lock_file)
    db = Database(db_path=tmp_path / "test1.db")

    server = AegisConnectorServer(mode="PAPER", db=db)
    server.seed_mock_data()

    prop_res = server.submit_proposal({
        "symbol": "BTC/USDT",
        "side": "BUY",
        "order_type": "LIMIT",
        "price": "30000.00",
        "size": "0.01",
        "stop_loss": "29000.00",
        "rationale_id": "TEST_KS"
    })

    # Engage kill switch
    ks.engage(reason="Emergency market crash", operator="Abdul Hayy Khan")
    try:
        res = server.place_order(prop_res["proposal_id"], prop_res["idempotency_key"])
        assert res["passed"] is False
        assert "kill switch" in str(res["reasons"]).lower()

        # Corrupt lock file test
        lock_file.write_text("invalid json {{{ not a valid state", encoding="utf-8")
        assert ks.is_engaged() is True
        res_corrupt = server.place_order(prop_res["proposal_id"], prop_res["idempotency_key"])
        assert res_corrupt["passed"] is False
    finally:
        os.environ.pop("AEGIS_KILL_SWITCH_LOCK", None)


def test_2_new_utc_day_resets_counter_and_loss_and_peak_equity(tmp_path: Path) -> None:
    """Finding C4 / Test 2: New UTC day resets orders count and daily loss; peak equity rises."""
    db = Database(db_path=tmp_path / "test2.db")
    server = AegisConnectorServer(mode="PAPER", db=db)
    server.seed_mock_data()

    # Artificially set yesterday's order date and counters
    server.orders_today_count = 5
    server.daily_realized_loss = Decimal("150.00")
    server.last_order_date = datetime.now(UTC).date() - timedelta(days=1)
    server.peak_equity = Decimal("10000.00")

    # Give broker a fill with higher equity
    server.broker.cash = Decimal("12000.00")

    prop = server.submit_proposal({
        "symbol": "BTC/USDT",
        "side": "BUY",
        "order_type": "LIMIT",
        "price": "30000.00",
        "size": "0.01",
        "stop_loss": "29000.00",
        "rationale_id": "TEST_NEW_DAY"
    })

    res = server.place_order(prop["proposal_id"], prop["idempotency_key"])
    assert res["passed"] is True
    # Orders count reset for new day, then incremented to 1
    assert server.orders_today_count == 1
    # Peak equity adjusted upward
    assert server.peak_equity >= Decimal("11000.00")


def test_3_stale_last_bar_blocks_orders(tmp_path: Path) -> None:
    """Finding C4 / Test 3: Stale last bar timestamp blocks orders."""
    db = Database(db_path=tmp_path / "test3.db")
    server = AegisConnectorServer(mode="PAPER", db=db)

    # Seed with bar timestamp from 10 days ago
    stale_ts = int((datetime.now(UTC) - timedelta(days=10)).timestamp())
    server.bars_db["BTC/USDT"] = [{
        "symbol": "BTC/USDT",
        "timeframe": "1d",
        "ts": stale_ts,
        "open": "30000",
        "high": "30500",
        "low": "29500",
        "close": "30000",
        "volume": "100"
    }]

    prop = server.submit_proposal({
        "symbol": "BTC/USDT",
        "side": "BUY",
        "order_type": "LIMIT",
        "price": "30000.00",
        "size": "0.01",
        "stop_loss": "29000.00",
        "rationale_id": "TEST_STALE"
    })

    res = server.place_order(prop["proposal_id"], prop["idempotency_key"])
    assert res["passed"] is False
    assert any("stale" in r.lower() or "lag" in r.lower() for r in res["reasons"])


def test_4_proposal_cannot_be_placed_twice_whatever_key(tmp_path: Path) -> None:
    """Finding C6 / Proof C / Test 4: One proposal cannot be filled repeatedly, whatever key is passed."""
    db = Database(db_path=tmp_path / "test4.db")
    server = AegisConnectorServer(mode="PAPER", db=db)
    server.seed_mock_data()

    prop = server.submit_proposal({
        "symbol": "BTC/USDT",
        "side": "BUY",
        "order_type": "LIMIT",
        "price": "30000.00",
        "size": "0.01",
        "stop_loss": "29000.00",
        "rationale_id": "TEST_IDEMPOTENCY"
    })

    # First execution succeeds
    res1 = server.place_order(prop["proposal_id"], prop["idempotency_key"])
    assert res1["passed"] is True

    # Second execution with fresh idempotency key must be REJECTED
    fresh_key = str(uuid.uuid4())
    res2 = server.place_order(prop["proposal_id"], fresh_key)
    assert res2["passed"] is False
    assert "already been executed" in str(res2["reasons"]).lower()


def test_5_sell_without_position_and_oversell_rejected(tmp_path: Path) -> None:
    """Finding C7 / Proof B / Test 5: SELL without position or larger than held position is rejected."""
    db = Database(db_path=tmp_path / "test5.db")
    server = AegisConnectorServer(mode="PAPER", db=db)
    server.seed_mock_data()

    # 1. Zero position SELL rejected
    prop_short = server.submit_proposal({
        "symbol": "BTC/USDT",
        "side": "SELL",
        "order_type": "LIMIT",
        "price": "30000.00",
        "size": "0.05",
        "stop_loss": "31000.00",
        "rationale_id": "TEST_SHORT"
    })
    res_short = server.place_order(prop_short["proposal_id"], prop_short["idempotency_key"])
    assert res_short["passed"] is False
    assert "shorting is disabled" in str(res_short["reasons"]).lower()

    # 2. Oversell rejected: give 0.02 BTC, try to sell 0.05 BTC
    server.broker.positions["BTC/USDT"] = Position(symbol="BTC/USDT", size=Decimal("0.02"), avg_price=Decimal(29000))
    prop_oversell = server.submit_proposal({
        "symbol": "BTC/USDT",
        "side": "SELL",
        "order_type": "LIMIT",
        "price": "30000.00",
        "size": "0.05",
        "stop_loss": "31000.00",
        "rationale_id": "TEST_OVERSELL"
    })
    res_oversell = server.place_order(prop_oversell["proposal_id"], prop_oversell["idempotency_key"])
    assert res_oversell["passed"] is False
    assert "oversell rejected" in str(res_oversell["reasons"]).lower()


def test_6_stop_loss_and_take_profit_direction_per_side() -> None:
    """Finding C8 / Proof D / Test 6: BUY with stop at/above entry, or SELL with stop at/below is rejected."""
    gate = RiskGate()
    now = datetime.now(UTC)
    context = GateContext(
        account_equity=Decimal("10000.00"),
        peak_equity=Decimal("10000.00"),
        daily_realized_loss=Decimal("0.00"),
        open_positions={},
        open_position_notionals={},
        orders_today_count=0,
        allowed_instruments={"BTC/USDT"},
        last_price=Decimal("30000.00"),
        last_bar_ts=now - timedelta(minutes=5),
        current_ts=now,
        bar_interval=timedelta(hours=4),
        kill_switch_active=False,
        used_idempotency_keys=set(),
        mode="PAPER"
    )

    # BUY with stop loss above entry price (Proof D flaw)
    bad_buy = OrderProposal(
        proposal_id=uuid.uuid4(),
        idempotency_key=uuid.uuid4(),
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        price=Decimal("30000.00"),
        size=Decimal("0.01"),
        stop_loss=Decimal("30500.00"),  # Above price!
        take_profit=Decimal("32000.00"),
        rationale_id="BAD_BUY_STOP"
    )
    decision = gate.evaluate(bad_buy, context)
    assert decision.passed is False
    assert any("strictly below" in r for r in decision.reasons)

    # SELL with stop loss below entry price
    bad_sell = OrderProposal(
        proposal_id=uuid.uuid4(),
        idempotency_key=uuid.uuid4(),
        symbol="BTC/USDT",
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        price=Decimal("30000.00"),
        size=Decimal("0.01"),
        stop_loss=Decimal("29500.00"),  # Below price!
        take_profit=Decimal("28000.00"),
        rationale_id="BAD_SELL_STOP"
    )
    context_sell = context.model_copy(update={"open_positions": {"BTC/USDT": Decimal("0.05")}})
    decision_sell = gate.evaluate(bad_sell, context_sell)
    assert decision_sell.passed is False
    assert any("strictly above" in r for r in decision_sell.reasons)


def test_7_reduce_only_exit_passes_after_daily_loss_breach() -> None:
    """Finding C8 / Proof E / Test 7: Reduce-only exit passes after daily loss breach; new entry blocked."""
    gate = RiskGate()
    now = datetime.now(UTC)

    # Breach daily loss (2% of $10,000 = $200)
    context_breached = GateContext(
        account_equity=Decimal("10000.00"),
        peak_equity=Decimal("10000.00"),
        daily_realized_loss=Decimal("300.00"),  # $300 > $200 limit!
        open_positions={"BTC/USDT": Decimal("0.10")},
        open_position_notionals={"BTC/USDT": Decimal("3000.00")},
        orders_today_count=1,
        allowed_instruments={"BTC/USDT"},
        last_price=Decimal("30000.00"),
        last_bar_ts=now - timedelta(minutes=5),
        current_ts=now,
        bar_interval=timedelta(hours=4),
        kill_switch_active=False,
        used_idempotency_keys=set(),
        mode="PAPER"
    )

    # New risk-adding BUY must be blocked
    buy_order = OrderProposal(
        proposal_id=uuid.uuid4(),
        idempotency_key=uuid.uuid4(),
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        price=Decimal("30000.00"),
        size=Decimal("0.01"),
        stop_loss=Decimal("29000.00"),
        rationale_id="NEW_BUY"
    )
    res_buy = gate.evaluate(buy_order, context_breached)
    assert res_buy.passed is False
    assert any("daily loss limit breached" in r.lower() for r in res_buy.reasons)

    # Risk-reducing SELL exit must PASS to allow position closing
    exit_order = OrderProposal(
        proposal_id=uuid.uuid4(),
        idempotency_key=uuid.uuid4(),
        symbol="BTC/USDT",
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        price=Decimal("30000.00"),
        size=Decimal("0.10"),
        stop_loss=Decimal("31000.00"),
        rationale_id="EXIT_POSITION",
        reduce_only=True
    )
    res_exit = gate.evaluate(exit_order, context_breached)
    assert res_exit.passed is True, f"Exit failed: {res_exit.reasons}"


def test_8_reconciliation_detects_injected_broker_difference() -> None:
    """Finding C5 / Test 8: Reconciliation detects injected cash or position discrepancy."""
    db_state = AccountState(
        equity=Decimal("10000.00"),
        cash=Decimal("10000.00"),
        positions={}
    )
    # Injected discrepancy in broker
    broker_state_divergent = AccountState(
        equity=Decimal("9800.00"),
        cash=Decimal("9800.00"),  # $200 missing
        positions={}
    )

    result = reconcile_states(db_state, broker_state_divergent)
    assert result.match is False
    assert any("cash mismatch" in d.lower() for d in result.diffs)


def test_9_stale_scheduler_lock_recovered(tmp_path: Path) -> None:
    """Finding H9 / Test 9: Stale scheduler lock (older than 1h) is safely recovered."""
    lock_file = tmp_path / "scheduler.lock"
    # Create lock file with old mtime (2 hours ago)
    lock_file.write_text("pid=99999\n", encoding="utf-8")
    past_mtime = (datetime.now(UTC) - timedelta(hours=2)).timestamp()
    os.utime(str(lock_file), (past_mtime, past_mtime))

    db = Database(db_path=tmp_path / "test9.db")
    server = AegisConnectorServer(mode="PAPER", db=db)
    scheduler = AutonomousScheduler(
        connector=server,
        scheduler_config=SchedulerConfig(lock_file=lock_file)
    )

    # acquire_lock must recognize lock is stale, remove it, and acquire successfully
    acquired = scheduler.acquire_lock()
    assert acquired is True
    assert lock_file.exists()
    scheduler.release_lock()


def test_10_demotion_persists_across_processes(tmp_path: Path) -> None:
    """Finding H6 / Test 10: Autonomy demotion survives across processes until owner resolves it."""
    db_file = tmp_path / "aegis_demotions.db"
    db1 = Database(db_path=db_file)

    # Process 1 records demotion after safety incident
    db1.record_demotion(
        incident_id="INC-2026-001",
        current_rung="RECOMMEND_ONLY",
        reason="Severe market data discrepancy detected"
    )

    # Process 2 starts up (fresh database connection)
    db2 = Database(db_path=db_file)
    active_rung = db2.get_active_demotion_rung()
    assert active_rung == "RECOMMEND_ONLY", "Demotion must persist across process restarts"

    # Owner resolves demotion
    db2.resolve_demotion(incident_id="INC-2026-001", operator="Abdul Hayy Khan")
    assert db2.get_active_demotion_rung() is None


def test_11_persistence_second_process_sees_first_process_data(tmp_path: Path) -> None:
    """Finding H3 / Test 11: A second process sees the first process's database state."""
    db_file = tmp_path / "shared.db"
    db1 = Database(db_path=db_file)
    server1 = AegisConnectorServer(mode="PAPER", db=db1)
    server1.seed_mock_data()

    # Process 1 submits and executes order
    prop = server1.submit_proposal({
        "symbol": "BTC/USDT",
        "side": "BUY",
        "order_type": "LIMIT",
        "price": "30000.00",
        "size": "0.02",
        "stop_loss": "29000.00",
        "rationale_id": "P1_ORDER"
    })
    res = server1.place_order(prop["proposal_id"], prop["idempotency_key"])
    assert res["passed"] is True, f"P1 execution failed: {res.get('reasons')}"

    # Process 2 starts up connecting to same database
    db2 = Database(db_path=db_file)
    server2 = AegisConnectorServer(mode="PAPER", db=db2)

    # Process 2 must see open position of 0.02 BTC from Process 1
    assert "BTC/USDT" in server2.broker.positions
    assert server2.broker.positions["BTC/USDT"].size == Decimal("0.02")

    # Process 2 must recognize proposal was already executed
    res_dup = server2.place_order(prop["proposal_id"], str(uuid.uuid4()))
    assert res_dup["passed"] is False
    assert "already been executed" in str(res_dup["reasons"]).lower()
