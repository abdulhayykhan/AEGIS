from decimal import Decimal

from src.agent.loop import AgentConfig, AgentLoop
from src.connector.server import AegisConnectorServer


def test_agent_loop_turn_limit_enforced() -> None:
    """Verify agent loop strictly halts if max turns (default 12) is reached."""
    server = AegisConnectorServer(mode="PAPER")
    server.seed_mock_data()

    config = AgentConfig(
        max_turns=3,  # Strict low limit
        cost_cap_usd=Decimal("1.00"),
        mode="RECOMMEND_ONLY"
    )
    agent = AgentLoop(connector=server, config=config)

    # Force artificial turn progression
    result = agent.execute_cycle(force_turns=4)
    assert result.turns_executed <= 3
    assert result.status == "STOPPED"
    assert "turn limit" in result.stop_reason.lower()


def test_agent_loop_cost_cap_enforced() -> None:
    """Verify agent loop halts if estimated cost breaches USD 1.00 cap."""
    server = AegisConnectorServer(mode="PAPER")
    server.seed_mock_data()

    config = AgentConfig(
        max_turns=12,
        cost_cap_usd=Decimal("0.05"),  # Very low cost limit
        mode="RECOMMEND_ONLY"
    )
    agent = AgentLoop(connector=server, config=config)

    result = agent.execute_cycle(mock_cost_per_turn=Decimal("0.03"))
    assert result.cost_usd <= Decimal("0.06")
    assert result.status == "STOPPED"
    assert "cost cap" in result.stop_reason.lower()


def test_agent_loop_recommend_only_disallows_order_placement() -> None:
    """Verify that in Phase 5 RECOMMEND_ONLY mode, agent cannot execute live/paper orders."""
    server = AegisConnectorServer(mode="PAPER")
    server.seed_mock_data()

    config = AgentConfig(
        max_turns=12,
        cost_cap_usd=Decimal("1.00"),
        mode="RECOMMEND_ONLY"
    )
    agent = AgentLoop(connector=server, config=config)

    result = agent.execute_cycle()
    assert result.orders_placed_count == 0
    assert result.proposals_generated_count >= 0


def test_agent_loop_with_council_deliberation() -> None:
    """Verify that when enable_council=True, council deliberation runs and gates proposals."""
    server = AegisConnectorServer(mode="PAPER")
    server.seed_mock_data()

    config = AgentConfig(
        max_turns=12,
        cost_cap_usd=Decimal("1.00"),
        mode="RECOMMEND_ONLY",
        enable_council=True,
        min_conviction=Decimal("0.70")
    )
    agent = AgentLoop(connector=server, config=config)

    result = agent.execute_cycle()
    assert result.status == "SUCCESS"
    assert result.orders_placed_count == 0


def test_agent_loop_council_bear_warning_suppresses_proposal() -> None:
    """Verify that severe bear warnings (e.g. whale distribution) suppress proposal creation."""
    server = AegisConnectorServer(mode="PAPER")
    server.seed_mock_data()

    # Simulate heavy exchange netflow inflow (distribution)
    server.get_onchain_flow = lambda symbol: {  # type: ignore[method-assign]
        "symbol": symbol,
        "exchange_netflow_usd": "50000000.00",
        "whale_accumulation_score": "20.0",
        "dex_liquidity_change_pct": "-10.0",
        "smart_money_bias": "DISTRIBUTION_BEARISH"
    }

    config = AgentConfig(
        max_turns=12,
        cost_cap_usd=Decimal("1.00"),
        mode="RECOMMEND_ONLY",
        enable_council=True,
        min_conviction=Decimal("0.70")
    )
    agent = AgentLoop(connector=server, config=config)

    result = agent.execute_cycle()
    assert result.status == "SUCCESS"
    assert result.proposals_generated_count == 0, "Bear warning must suppress proposal creation"
