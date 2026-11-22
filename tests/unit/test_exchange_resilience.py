"""Tests for exchange venue client resilience: retries, backoff, and rate-limiting.

Built by [Abdul Hayy Khan](https://abdulhayykhan.dev).
Citations & inspirations:
- AEGIS Project Review Report (Finding M4 & Section 5 Step 3.1)
"""

import pytest

from src.connector.broker import ExchangeVenueConfig, PluggableExchangeBroker


def test_exchange_retry_on_transient_failure() -> None:
    config = ExchangeVenueConfig(
        venue_name="BINANCE_TESTNET",
        api_endpoint="https://testnet.binance.vision",
        max_retries=3,
        backoff_factor=0.01
    )
    broker = PluggableExchangeBroker(venue_config=config)

    attempts = 0

    def flaky_operation() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ConnectionResetError("Transient network drop")
        return "SUCCESS"

    result = broker.execute_with_retry(flaky_operation)
    assert result == "SUCCESS"
    assert attempts == 3


def test_exchange_exceeds_max_retries_raises() -> None:
    config = ExchangeVenueConfig(
        venue_name="BINANCE_TESTNET",
        api_endpoint="https://testnet.binance.vision",
        max_retries=2,
        backoff_factor=0.01
    )
    broker = PluggableExchangeBroker(venue_config=config)

    def failing_operation() -> str:
        raise TimeoutError("Exchange gateway timeout")

    with pytest.raises(TimeoutError, match="Exchange gateway timeout"):
        broker.execute_with_retry(failing_operation)


def test_exchange_rate_limiter_throttles() -> None:
    config = ExchangeVenueConfig(
        venue_name="BINANCE_TESTNET",
        api_endpoint="https://testnet.binance.vision",
        rate_limit_req_per_sec=100
    )
    broker = PluggableExchangeBroker(venue_config=config)

    # Calling check_rate_limit consumes capacity
    assert broker.check_rate_limit() is True
