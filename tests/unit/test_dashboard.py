from decimal import Decimal
from pathlib import Path

from ops.dashboard import AegisDashboard
from ops.run_paper_simulation import run_paper_execution_simulation
from src.connector.server import AegisConnectorServer


def test_dashboard_renders_metrics_and_markdown() -> None:
    server = AegisConnectorServer(mode="PAPER")
    server.seed_mock_data()

    dashboard = AegisDashboard(connector=server)
    metrics = dashboard.get_metrics()

    assert metrics.equity == Decimal("10000.00")
    assert metrics.orders_today_count == 0
    assert metrics.kill_switch_active is False
    assert metrics.reconciliation_matched is True

    md = dashboard.render_markdown()
    assert "AEGIS Operations Dashboard" in md
    assert "Emergency Kill Switch" in md
    assert "DSoR Reconciliation" in md
    assert "Total Account Equity" in md


def test_paper_execution_simulation_short_run(tmp_path: Path) -> None:
    report_file = tmp_path / "sim_report.md"
    res = run_paper_execution_simulation(num_days=3, output_report_path=report_file)

    assert res["num_days"] == 3
    assert res["successful_days"] == 3
    assert res["total_violations"] == 0
    assert res["reconciliations_matched"] == 3
    assert report_file.exists()
