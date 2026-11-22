from decimal import Decimal

import pytest

from src.connector.server import AegisConnectorServer
from src.gate.models import OrderSide, OrderType

FORBIDDEN_TOOLS = ["withdraw", "transfer", "set_limit", "set_mode", "execute_raw"]
REQUIRED_TOOLS = [
    "get_bars",
    "get_account",
    "get_open_orders",
    "get_news",
    "submit_proposal",
    "place_order",
    "cancel_order",
    "get_run_state"
]


@pytest.fixture
def connector() -> AegisConnectorServer:
    server = AegisConnectorServer(mode="PAPER")
    server.seed_mock_data()
    return server


def test_forbidden_tools_absent(connector: AegisConnectorServer) -> None:
    """Exit Criteria: Verify that NO forbidden tools exist on the MCP connector server."""
    registered_tools = connector.list_tools()
    for forbidden in FORBIDDEN_TOOLS:
        assert forbidden not in registered_tools, f"CRITICAL: Forbidden tool '{forbidden}' found on server!"


def test_required_tools_present(connector: AegisConnectorServer) -> None:
    """Verify all 8 approved tools from PRD Section 9 are registered."""
    registered_tools = connector.list_tools()
    for required in REQUIRED_TOOLS:
        assert required in registered_tools, f"Required tool '{required}' missing on server"


def test_contract_get_bars(connector: AegisConnectorServer) -> None:
    """Contract: get_bars returns valid OHLCV bars list."""
    bars = connector.get_bars(symbol="BTC/USDT", timeframe="1d", limit=10)
    assert len(bars) > 0
    assert "ts" in bars[0]
    assert "close" in bars[0]
    assert Decimal(str(bars[0]["close"])) > Decimal(0)


def test_contract_get_account(connector: AegisConnectorServer) -> None:
    """Contract: get_account returns equity, cash, positions in minor/Decimal format."""
    acc = connector.get_account()
    assert "equity" in acc
    assert "cash" in acc
    assert "positions" in acc
    assert Decimal(str(acc["equity"])) == Decimal("10000.00")


def test_contract_get_open_orders(connector: AegisConnectorServer) -> None:
    """Contract: get_open_orders returns list of open orders."""
    orders = connector.get_open_orders()
    assert isinstance(orders, list)


def test_contract_get_news_flagged_untrusted(connector: AegisConnectorServer) -> None:
    """Contract: get_news returns headlines and summaries explicitly flagged trust='untrusted'."""
    news = connector.get_news(symbol="BTC/USDT", since=0)
    assert len(news) > 0
    for item in news:
        assert item["trust"] == "untrusted"
        assert "title" in item
        assert "summary" in item


def test_contract_submit_proposal(connector: AegisConnectorServer) -> None:
    """Contract: submit_proposal validates and stores a proposal."""
    proposal_data = {
        "symbol": "BTC/USDT",
        "side": OrderSide.BUY.value,
        "order_type": OrderType.LIMIT.value,
        "price": "30000.00",
        "size": "0.033",
        "stop_loss": "29000.00",
        "take_profit": "32000.00",
        "rationale_id": "TREND_001"
    }
    result = connector.submit_proposal(proposal_data)
    assert result["stored"] is True
    assert "proposal_id" in result
    assert "idempotency_key" in result


def test_contract_place_order_gated_success(connector: AegisConnectorServer) -> None:
    """Case Matrix: Valid order passing all 8 gate checks executes paper fill."""
    proposal_data = {
        "symbol": "BTC/USDT",
        "side": OrderSide.BUY.value,
        "order_type": OrderType.LIMIT.value,
        "price": "30000.00",
        "size": "0.033",
        "stop_loss": "29000.00",
        "take_profit": "32000.00",
        "rationale_id": "TREND_001"
    }
    submission = connector.submit_proposal(proposal_data)
    prop_id = submission["proposal_id"]
    idem_key = submission["idempotency_key"]

    order_result = connector.place_order(proposal_id=prop_id, idempotency_key=idem_key)
    assert order_result["passed"] is True
    assert order_result["status"] in ("SUBMITTED", "FILLED")
    assert "order_id" in order_result


def test_contract_place_order_duplicate_key_rejected(connector: AegisConnectorServer) -> None:
    """Case Matrix: Duplicate idempotency key is rejected by gate."""
    proposal_data = {
        "symbol": "BTC/USDT",
        "side": OrderSide.BUY.value,
        "order_type": OrderType.LIMIT.value,
        "price": "30000.00",
        "size": "0.033",
        "stop_loss": "29000.00",
        "take_profit": "32000.00",
        "rationale_id": "TREND_001"
    }
    submission = connector.submit_proposal(proposal_data)
    prop_id = submission["proposal_id"]
    idem_key = submission["idempotency_key"]

    # First attempt: succeeds
    res1 = connector.place_order(proposal_id=prop_id, idempotency_key=idem_key)
    assert res1["passed"] is True

    # Second attempt with same idempotency key: rejected!
    res2 = connector.place_order(proposal_id=prop_id, idempotency_key=idem_key)
    assert res2["passed"] is False
    assert any("idempotency key" in r.lower() for r in res2["reasons"])


def test_contract_place_order_over_limit_rejected(connector: AegisConnectorServer) -> None:
    """Case Matrix: Proposal exceeding 1% trade risk is rejected by gate."""
    # 5% risk ($500 risk > $100 budget)
    proposal_data = {
        "symbol": "BTC/USDT",
        "side": OrderSide.BUY.value,
        "order_type": OrderType.LIMIT.value,
        "price": "30000.00",
        "size": "0.033",
        "stop_loss": "15000.00",  # $15,000 distance * 0.033 = ~$495 risk
        "take_profit": "35000.00",
        "rationale_id": "OVER_RISK"
    }
    submission = connector.submit_proposal(proposal_data)
    prop_id = submission["proposal_id"]
    idem_key = submission["idempotency_key"]

    res = connector.place_order(proposal_id=prop_id, idempotency_key=idem_key)
    assert res["passed"] is False
    assert any("risk per trade" in r.lower() for r in res["reasons"])


def test_contract_cancel_order(connector: AegisConnectorServer) -> None:
    """Contract: cancel_order cancels an active open order."""
    # Mark price = 30,000. Price = 29,700 (1% below mark price -> passes 2% price sanity, remains open limit)
    proposal_data = {
        "symbol": "BTC/USDT",
        "side": OrderSide.BUY.value,
        "order_type": OrderType.LIMIT.value,
        "price": "29700.00",
        "size": "0.033",
        "stop_loss": "28800.00",
        "take_profit": "32000.00",
        "rationale_id": "OPEN_LIMIT"
    }
    submission = connector.submit_proposal(proposal_data)
    res = connector.place_order(proposal_id=submission["proposal_id"], idempotency_key=submission["idempotency_key"])
    assert res["passed"] is True
    order_id = res["order_id"]

    cancel_res = connector.cancel_order(order_id=order_id)
    assert cancel_res["cancelled"] is True



def test_contract_get_run_state(connector: AegisConnectorServer) -> None:
    """Contract: get_run_state returns today's counters, daily PnL, remaining limits."""
    state = connector.get_run_state()
    assert "orders_today_count" in state
    assert "daily_realized_loss" in state
    assert "remaining_risk_budget" in state
    assert "kill_switch_active" in state
