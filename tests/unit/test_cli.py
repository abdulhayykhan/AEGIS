import sys
from pathlib import Path

import pytest

from src.cli import main


def test_cli_dashboard(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(sys, "argv", ["aegis", "dashboard"])
    exit_code = main()
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "AEGIS Operations Dashboard" in captured.out
    assert "Emergency Kill Switch" in captured.out


def test_cli_run_cycle(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(sys, "argv", ["aegis", "run", "--mode", "RECOMMEND_ONLY"])
    exit_code = main()
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Run completed with status" in captured.out


def test_cli_kill_switch(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    test_lock = tmp_path / "test_kill.lock"
    # Engage
    monkeypatch.setattr(sys, "argv", ["aegis", "kill", "--reason", "Test Emergency", "--owner", "Abdul Hayy Khan", "--lock-path", str(test_lock)])
    exit_code = main()
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Kill switch ENGAGED" in captured.out
    assert test_lock.exists()

    # Disengage
    monkeypatch.setattr(sys, "argv", ["aegis", "kill", "--disengage", "--owner", "Abdul Hayy Khan", "--lock-path", str(test_lock)])
    exit_code = main()
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Kill switch DISENGAGED" in captured.out
    assert not test_lock.exists()


def test_cli_reconcile(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(sys, "argv", ["aegis", "reconcile"])
    exit_code = main()
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "RECONCILIATION RESULT" in captured.out
    assert "MATCH" in captured.out


def test_cli_promote(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(sys, "argv", ["aegis", "promote", "--target", "PAPER_EXECUTION"])
    # Without runs, promotion returns 1 (refused) safely
    exit_code = main()
    assert exit_code in (0, 1)
    captured = capsys.readouterr()
    assert "AUTONOMY PROMOTION CHECK" in captured.out


def test_cli_report(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(sys, "argv", ["aegis", "report"])
    exit_code = main()
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Weekly Performance Report" in captured.out
