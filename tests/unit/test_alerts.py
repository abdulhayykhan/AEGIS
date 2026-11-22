from decimal import Decimal

from ops.alerts import AlertLevel, AlertService


def test_alerts_approaching_limit_warning() -> None:
    """Verify 80% limit warning alert is formatted and dispatched."""
    alert_service = AlertService(telegram_token=None, chat_id=None)  # Offline / mock mode

    msg = alert_service.notify_limit_approaching(
        limit_name="Daily Loss Limit",
        current_val=Decimal("165.00"),
        threshold_val=Decimal("200.00"),
        pct_used=Decimal("82.5")
    )

    assert msg.level == AlertLevel.WARNING
    assert "82.5%" in msg.text
    assert "Daily Loss Limit" in msg.text
    assert len(alert_service.get_history()) == 1


def test_alerts_reconciliation_mismatch() -> None:
    """Verify high-priority alert on reconciliation divergence."""
    alert_service = AlertService(telegram_token=None, chat_id=None)

    msg = alert_service.notify_reconciliation_mismatch(
        diffs=["Cash mismatch: DB=10000 vs Broker=9950"]
    )

    assert msg.level == AlertLevel.CRITICAL
    assert "RECONCILIATION MISMATCH" in msg.text
    assert "Cash mismatch" in msg.text


def test_alerts_heartbeat_dispatch() -> None:
    """Verify daily heartbeat message structure."""
    alert_service = AlertService(telegram_token=None, chat_id=None)

    msg = alert_service.notify_heartbeat(
        equity=Decimal("10000.00"),
        daily_pnl=Decimal("35.50"),
        open_positions_count=1,
        status="HEALTHY"
    )

    assert msg.level == AlertLevel.INFO
    assert "HEARTBEAT" in msg.text
    assert "10000.00 USDT" in msg.text
