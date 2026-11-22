from datetime import datetime, timedelta


def verify_bar_freshness(
    latest_bar_ts: datetime,
    current_ts: datetime,
    bar_interval: timedelta,
    max_bars_lag: int = 2
) -> tuple[bool, str]:
    """Verify whether the latest bar timestamp is within acceptable freshness boundaries.
    
    Rule: Reject if the latest price is older than `max_bars_lag` bars.
    """
    max_allowed_lag = bar_interval * max_bars_lag
    elapsed = current_ts - latest_bar_ts

    if elapsed < timedelta(0):
        return False, f"Invalid future timestamp on bar: {latest_bar_ts} > {current_ts}"

    if elapsed > max_allowed_lag:
        return False, f"Stale market data: latest bar was {elapsed} ago (max allowed {max_allowed_lag})"

    return True, "OK"
