from decimal import Decimal
from pathlib import Path

from ops.alerts import AlertLevel, AlertService
from ops.scheduler import AutonomousScheduler, SchedulerConfig
from src.agent.loop import AgentConfig, AgentLoop
from src.connector.server import AegisConnectorServer


def test_full_autonomy_places_orders_inside_limits() -> None:
    """Verify that in FULL_AUTONOMY mode, orders are executed autonomously within risk limits."""
    server = AegisConnectorServer(mode="LIVE")
    server.seed_mock_data()

    config = AgentConfig(
        max_turns=12,
        cost_cap_usd=Decimal("1.00"),
        mode="FULL_AUTONOMY"
    )
    agent = AgentLoop(connector=server, config=config)

    result = agent.execute_cycle()
    assert result.status == "SUCCESS"
    assert result.orders_placed_count >= 1

    # Check broker has active position or order
    acc = server.get_account()
    has_activity = (len(server.get_open_orders()) > 0) or (len(acc["positions"]) > 0)
    assert has_activity is True


def test_demotion_on_risk_violation(tmp_path: Path) -> None:
    """Verify that any risk violation or reconciliation failure drops an autonomy rung (PRD Section 17)."""
    server = AegisConnectorServer(mode="LIVE")
    server.seed_mock_data()
    # Artificially trigger daily realized loss breach to force risk gate rejection
    server.daily_realized_loss = Decimal("350.00")  # Exceeds $200 limit

    alert_service = AlertService()
    sched_config = SchedulerConfig(lock_file=tmp_path / "demotion.lock")
    agent_config = AgentConfig(mode="FULL_AUTONOMY")

    scheduler = AutonomousScheduler(
        connector=server,
        scheduler_config=sched_config,
        agent_config=agent_config,
        alert_service=alert_service
    )

    report = scheduler.run_scheduled_cycle()
    assert report.success is False
    # Check that autonomous execution failed safe and triggered demotion
    assert scheduler.agent_config.mode in ("RECOMMEND_ONLY", "STOPPED")

    # Check alert history contains demotion notification
    history = alert_service.get_history()
    demotion_alerts = [m for m in history if "DEMOTION" in m.text or m.level == AlertLevel.CRITICAL]
    assert len(demotion_alerts) >= 1
