import json
from decimal import Decimal
from pathlib import Path

import pytest

from ops.weekly_report import generate_weekly_report
from src.storage.db import Database
from src.utils.logging import AegisJsonFormatter, get_logger


def test_event_ledger_append_and_replay(tmp_path: Path) -> None:
    db = Database(db_path=tmp_path / "event_test.db")

    # Record append-only events
    ev1 = db.record_event(
        event_type="PROPOSAL_SUBMITTED",
        aggregate_id="PROP-001",
        payload={"symbol": "BTC/USDT", "side": "BUY", "size": "0.02"}
    )
    ev2 = db.record_event(
        event_type="ORDER_FILLED",
        aggregate_id="ORD-001",
        payload={"symbol": "BTC/USDT", "fill_price": "30000.00", "size": "0.02", "fee": "0.60"}
    )

    events = db.get_events()
    assert len(events) == 2
    assert events[0]["event_id"] == ev1
    assert events[1]["event_id"] == ev2
    assert json.loads(events[1]["payload_json"])["fill_price"] == "30000.00"

    # Replay
    replayed = db.replay_events()
    assert len(replayed) == 2
    assert replayed[0]["event_type"] == "PROPOSAL_SUBMITTED"


def test_structured_json_logging(capsys: pytest.CaptureFixture[str]) -> None:
    logger = get_logger("aegis.test")
    logger.info("Structured event triggered", extra={"component": "Gate", "symbol": "BTC/USDT"})

    # Check logger has JSON formatter
    assert any(isinstance(h.formatter, AegisJsonFormatter) for h in logger.handlers)


def test_weekly_performance_report_generation(tmp_path: Path) -> None:
    db = Database(db_path=tmp_path / "report_test.db")
    # Record mock fills
    db.record_fill({
        "order_id": "ORD-01",
        "symbol": "BTC/USDT",
        "side": "BUY",
        "price": "30000.00",
        "size": "0.01",
        "fee": "0.30",
        "filled_at": "2026-11-20T10:00:00Z"
    })
    db.record_fill({
        "order_id": "ORD-02",
        "symbol": "BTC/USDT",
        "side": "SELL",
        "price": "31000.00",
        "size": "0.01",
        "fee": "0.31",
        "filled_at": "2026-11-21T10:00:00Z"
    })

    report = generate_weekly_report(db)
    assert report.total_trades == 2
    assert report.total_fees == Decimal("0.61")
    assert report.net_realized_pnl == Decimal("9.39")  # 10.00 gross - 0.61 fees
    assert "Weekly Performance Report" in report.to_markdown()
