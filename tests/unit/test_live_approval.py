import uuid
from decimal import Decimal
from pathlib import Path

from src.agent.loop import AgentConfig, AgentLoop
from src.connector.server import AegisConnectorServer


def test_live_with_approval_mode_drafts_order_without_executing() -> None:
    """Verify that in LIVE_WITH_APPROVAL mode, orders are drafted and held pending owner approval."""
    server = AegisConnectorServer(mode="LIVE_WITH_APPROVAL")
    server.seed_mock_data()

    config = AgentConfig(
        max_turns=12,
        cost_cap_usd=Decimal("1.00"),
        mode="LIVE_WITH_APPROVAL"
    )
    agent = AgentLoop(connector=server, config=config)

    result = agent.execute_cycle()
    assert result.status == "SUCCESS"
    assert result.proposals_generated_count >= 1
    # Crucial: 0 orders placed directly by agent in this mode
    assert result.orders_placed_count == 0

    # Verify drafted proposal exists in pending approval state
    pending_drafts = server.get_pending_approvals()
    assert len(pending_drafts) >= 1
    assert pending_drafts[0]["status"] == "PENDING_APPROVAL"


def test_owner_approval_routes_through_risk_gate_to_broker() -> None:
    """Verify that owner approval with valid token safely executes through the Risk Gate."""
    server = AegisConnectorServer(mode="LIVE_WITH_APPROVAL")
    server.seed_mock_data()

    # Draft a proposal directly
    prop_payload = {
        "symbol": "BTC/USDT",
        "side": "BUY",
        "order_type": "LIMIT",
        "price": "30000.00",
        "size": "0.01",
        "stop_loss": "29400.00",
        "take_profit": "30800.00",
        "rationale_id": "TEST_LIVE_APPROVAL"
    }
    sub = server.submit_proposal(prop_payload)
    proposal_id = uuid.UUID(sub["proposal_id"])

    # 1. Reject execution without valid approval token
    invalid_res = server.approve_and_place_order(proposal_id=proposal_id, approval_token="WRONG_TOKEN")
    assert invalid_res["passed"] is False
    assert "Invalid or missing owner approval token" in invalid_res["reasons"][0]

    # 2. Accept execution with valid owner signature
    valid_res = server.approve_and_place_order(
        proposal_id=proposal_id,
        approval_token="OWNER_ABDUL_HAYY_SIGNATURE"
    )
    assert valid_res["passed"] is True
    assert valid_res["order"]["status"] in ("FILLED", "SUBMITTED")


def test_slippage_monitoring_within_assumptions() -> None:
    """Verify slippage monitoring compares execution fill against expected mark price."""
    server = AegisConnectorServer(mode="LIVE_WITH_APPROVAL")
    server.seed_mock_data()

    prop_payload = {
        "symbol": "BTC/USDT",
        "side": "BUY",
        "order_type": "LIMIT",
        "price": "30000.00",
        "size": "0.01",
        "stop_loss": "29400.00",
        "take_profit": "30800.00",
        "rationale_id": "TEST_SLIPPAGE"
    }
    sub = server.submit_proposal(prop_payload)
    proposal_id = uuid.UUID(sub["proposal_id"])

    res = server.approve_and_place_order(
        proposal_id=proposal_id,
        approval_token="OWNER_ABDUL_HAYY_SIGNATURE"
    )
    assert res["passed"] is True
    # Verify slippage calculation is tracked
    assert "slippage_pct" in res
    assert res["slippage_pct"] <= Decimal("0.05")  # Within 0.05% backtest assumption


def test_live_approval_simulation_short_run(tmp_path: Path) -> None:
    from ops.run_live_approval_simulation import run_live_approval_simulation
    report_file = tmp_path / "live_sim_report.md"
    res = run_live_approval_simulation(num_days=3, output_report_path=report_file)

    assert res["num_days"] == 3
    assert res["successful_days"] == 3
    assert res["total_violations"] == 0
    assert res["reconciliations_matched"] == 3
    assert report_file.exists()
