from pathlib import Path

import pytest

from ops.scheduler import AutonomousScheduler, SchedulerConfig
from src.agent.loop import AgentConfig
from src.connector.server import AegisConnectorServer


@pytest.fixture
def temp_lock_path(tmp_path: Path) -> Path:
    return tmp_path / "scheduler.lock"


def test_scheduler_process_lock_prevents_overlapping_runs(temp_lock_path: Path) -> None:
    """Verify that two scheduled runs cannot run at the same time (PRD Section 15.1)."""
    server = AegisConnectorServer(mode="PAPER")
    server.seed_mock_data()

    sched_config = SchedulerConfig(lock_file=temp_lock_path)
    agent_config = AgentConfig(mode="PAPER_EXECUTION")

    scheduler1 = AutonomousScheduler(connector=server, scheduler_config=sched_config, agent_config=agent_config)
    scheduler2 = AutonomousScheduler(connector=server, scheduler_config=sched_config, agent_config=agent_config)

    # Acquire lock with scheduler 1
    assert scheduler1.acquire_lock() is True
    # Scheduler 2 cannot acquire lock simultaneously
    assert scheduler2.acquire_lock() is False

    # Once scheduler 1 releases lock, scheduler 2 can acquire
    scheduler1.release_lock()
    assert scheduler2.acquire_lock() is True
    scheduler2.release_lock()


def test_scheduler_enforces_ran_is_not_worked_conditions(temp_lock_path: Path) -> None:
    """Verify all 6 'ran is not worked' conditions must pass to mark run SUCCESS."""
    server = AegisConnectorServer(mode="PAPER")
    server.seed_mock_data()

    sched_config = SchedulerConfig(lock_file=temp_lock_path)
    agent_config = AgentConfig(mode="PAPER_EXECUTION")
    scheduler = AutonomousScheduler(connector=server, scheduler_config=sched_config, agent_config=agent_config)

    run_report = scheduler.run_scheduled_cycle()
    assert run_report.success is True
    assert run_report.checks["data_freshness_verified"] is True
    assert run_report.checks["pre_reconciliation_matched"] is True
    assert run_report.checks["post_reconciliation_matched"] is True
    assert run_report.checks["gate_decisions_recorded"] is True
    assert run_report.checks["recomputation_verified"] is True
