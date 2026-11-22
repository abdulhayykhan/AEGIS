from decimal import Decimal

import pytest

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


def test_external_dead_mans_switch_ping(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify external dead-man's switch webhook is dispatched on cycle execution."""
    recorded_urls: list[str] = []

    def mock_urlopen(req, timeout=5):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        recorded_urls.append(url)
        class DummyResp:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self): return b"OK"
        return DummyResp()

    monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)

    alert_service = AlertService(heartbeat_url="https://hc-ping.com/12345-mock-uuid")

    # 1. Success ping
    alert_service.ping_external_heartbeat(status="success")
    assert len(recorded_urls) == 1
    assert recorded_urls[0] == "https://hc-ping.com/12345-mock-uuid"

    # 2. Failure ping
    alert_service.ping_external_heartbeat(status="fail", message="Circuit breaker tripped")
    assert len(recorded_urls) == 2
    assert recorded_urls[1] == "https://hc-ping.com/12345-mock-uuid/fail"

