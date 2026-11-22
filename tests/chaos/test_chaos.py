"""AEGIS Chaos & Adversarial System Resiliency Test Suite.

Built by [Abdul Hayy Khan](https://abdulhayykhan.dev).
Citations:
- AEGIS Project Review Report (Section 6.2: Chaos Testing Suite)
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from src.connector.server import AegisConnectorServer
from src.gate.evaluator import RiskGate
from src.gate.models import GateContext, OrderProposal, OrderSide, OrderType
from src.signals.freshness import verify_bar_freshness


def test_chaos_broker_exception_handled_gracefully() -> None:
    server = AegisConnectorServer(mode="PAPER")
    server.seed_mock_data()

    # Sabotage broker place_order to simulate network breakdown
    def broken_place_order(*args, **kwargs):
        raise ConnectionResetError("Broker network connection dropped by peer.")

    server.broker.place_order = broken_place_order  # type: ignore

    prop = server.submit_proposal({
        "symbol": "BTC/USDT",
        "side": "BUY",
        "order_type": "LIMIT",
        "price": "30000.00",
        "size": "0.01",
        "stop_loss": "29000.00",
        "rationale_id": "CHAOS_BROKER_DOWN"
    })

    # Server must catch unexpected broker drop or raise clean operational error without DB corruption
    with pytest.raises(ConnectionResetError):
        server.place_order(prop["proposal_id"], prop["idempotency_key"])

    # State verification: proposal was not marked executed, cash was not deducted
    acc = server.get_account()
    assert Decimal(str(acc["cash"])) == Decimal("10000.00")
    assert not server.db.is_proposal_executed(uuid.UUID(prop["proposal_id"]))


def test_chaos_stale_feed_strictly_blocks_orders() -> None:
    now = datetime.now(UTC)
    # Feed is 48 hours old
    stale_bar_ts = now - timedelta(hours=48)

    ok, msg = verify_bar_freshness(
        latest_bar_ts=stale_bar_ts,
        current_ts=now,
        bar_interval=timedelta(hours=4),
        max_bars_lag=2
    )
    assert ok is False
    assert "Stale market data" in msg

    gate = RiskGate()
    context = GateContext(
        account_equity=Decimal("10000.00"),
        peak_equity=Decimal("10000.00"),
        daily_realized_loss=Decimal("0.00"),
        open_positions={},
        open_position_notionals={},
        orders_today_count=0,
        allowed_instruments={"BTC/USDT"},
        last_price=Decimal("30000.00"),
        last_bar_ts=stale_bar_ts,
        current_ts=now,
        bar_interval=timedelta(hours=4),
        kill_switch_active=False,
        used_idempotency_keys=set(),
        mode="PAPER"
    )
    order = OrderProposal(
        proposal_id=uuid.uuid4(),
        idempotency_key=uuid.uuid4(),
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        price=Decimal("30000.00"),
        size=Decimal("0.01"),
        stop_loss=Decimal("29000.00"),
        rationale_id="STALE_CHAOS"
    )
    dec = gate.evaluate(order, context)
    assert dec.passed is False
    assert any("stale" in r.lower() for r in dec.reasons)


def test_chaos_duplicate_burst_message_deduplication() -> None:
    server = AegisConnectorServer(mode="PAPER")
    server.seed_mock_data()

    prop = server.submit_proposal({
        "symbol": "BTC/USDT",
        "side": "BUY",
        "order_type": "LIMIT",
        "price": "30000.00",
        "size": "0.01",
        "stop_loss": "29000.00",
        "rationale_id": "BURST_TEST"
    })
    p_id = prop["proposal_id"]
    i_key = prop["idempotency_key"]

    # Burst of 10 identical execution calls in rapid succession
    results = [server.place_order(p_id, i_key) for _ in range(10)]

    # Exactly 1 must succeed, 9 must be rejected
    success_count = sum(1 for r in results if r.get("passed"))
    rejected_count = sum(1 for r in results if not r.get("passed"))
    assert success_count == 1
    assert rejected_count == 9

    # Exactly 1 position in broker
    assert "BTC/USDT" in server.broker.positions
    assert server.broker.positions["BTC/USDT"].size == Decimal("0.01")


def test_chaos_clock_skew_detection() -> None:
    # Future timestamp in bar relative to host clock (negative lag / time travel)
    now = datetime.now(UTC)
    future_bar_ts = now + timedelta(hours=2)

    ok, msg = verify_bar_freshness(
        latest_bar_ts=future_bar_ts,
        current_ts=now,
        bar_interval=timedelta(hours=1),
        max_bars_lag=2
    )
    # Future bar indicates dangerous clock skew or corrupted feed
    assert ok is False
    assert "Clock skew detected" in msg or "future" in msg.lower()
