from decimal import Decimal

from src.agent.loop import AgentConfig, AgentLoop
from src.connector.server import AegisConnectorServer


def test_paper_execution_places_orders_inside_limits() -> None:
    """Verify that in PAPER_EXECUTION mode, the agent places paper orders that pass the gate."""
    server = AegisConnectorServer(mode="PAPER")
    server.seed_mock_data()

    config = AgentConfig(
        max_turns=12,
        cost_cap_usd=Decimal("1.00"),
        mode="PAPER_EXECUTION"
    )
    agent = AgentLoop(connector=server, config=config)

    result = agent.execute_cycle()
    assert result.status == "SUCCESS"
    assert result.orders_placed_count >= 1

    # Check broker has filled or placed order
    account = server.get_account()
    open_orders = server.get_open_orders()
    has_activity = (len(open_orders) > 0) or (len(account["positions"]) > 0)
    assert has_activity is True, "Paper execution must produce valid broker activity"


def test_paper_execution_respects_kill_switch() -> None:
    """Verify that engaging the kill switch blocks paper execution immediately."""
    server = AegisConnectorServer(mode="PAPER")
    server.seed_mock_data()
    server.kill_switch_active = True

    config = AgentConfig(
        max_turns=12,
        cost_cap_usd=Decimal("1.00"),
        mode="PAPER_EXECUTION"
    )
    agent = AgentLoop(connector=server, config=config)

    result = agent.execute_cycle()
    assert result.status == "STOPPED"
    assert result.orders_placed_count == 0
    assert "kill switch" in result.stop_reason.lower()
