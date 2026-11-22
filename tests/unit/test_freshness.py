from datetime import UTC, datetime, timedelta

from src.signals.freshness import verify_bar_freshness


def test_freshness_valid():
    """Verify bar within 2 bar intervals is accepted as fresh."""
    now = datetime(2026, 11, 22, 12, 0, 0, tzinfo=UTC)
    # 4-hour bar interval; latest bar closed 1 hour ago
    bar_ts = now - timedelta(hours=1)
    bar_interval = timedelta(hours=4)

    is_fresh, reason = verify_bar_freshness(
        latest_bar_ts=bar_ts,
        current_ts=now,
        bar_interval=bar_interval,
        max_bars_lag=2
    )
    assert is_fresh is True
    assert reason == "OK"


def test_freshness_rejected_stale():
    """Verify bar older than 2 bar intervals is rejected."""
    now = datetime(2026, 11, 22, 12, 0, 0, tzinfo=UTC)
    # 4-hour bar interval; latest bar closed 9 hours ago (> 2 * 4h = 8h)
    bar_ts = now - timedelta(hours=9)
    bar_interval = timedelta(hours=4)

    is_fresh, reason = verify_bar_freshness(
        latest_bar_ts=bar_ts,
        current_ts=now,
        bar_interval=bar_interval,
        max_bars_lag=2
    )
    assert is_fresh is False
    assert "stale" in reason.lower()
