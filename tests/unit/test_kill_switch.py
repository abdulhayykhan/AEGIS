from pathlib import Path

import pytest

from src.gate.kill_switch import StandaloneKillSwitch


@pytest.fixture
def temp_kill_file(tmp_path: Path) -> Path:
    return tmp_path / "aegis_kill_switch.lock"


def test_kill_switch_engagement_and_persistence(temp_kill_file: Path) -> None:
    """Verify that kill switch engages atomically and persists state on disk."""
    ks = StandaloneKillSwitch(lock_file_path=temp_kill_file)
    assert ks.is_engaged() is False

    # Engage kill switch
    ks.engage(reason="Manual intervention by Abdul Hayy", operator="Abdul Hayy")
    assert ks.is_engaged() is True
    assert temp_kill_file.exists()

    # Re-reading from disk across a new instance (simulating stopped agent)
    ks_new = StandaloneKillSwitch(lock_file_path=temp_kill_file)
    assert ks_new.is_engaged() is True
    assert "Manual intervention" in ks_new.get_status().reason


def test_kill_switch_disengagement_by_owner(temp_kill_file: Path) -> None:
    """Verify that only authorized owner disengagement can clear the kill switch."""
    ks = StandaloneKillSwitch(lock_file_path=temp_kill_file)
    ks.engage(reason="Test", operator="Abdul Hayy")
    assert ks.is_engaged() is True

    # Agent cannot clear it; only authorized operator
    with pytest.raises(PermissionError, match="Unauthorized"):
        ks.disengage(operator="AI_AGENT")

    # Authorized owner disengages
    ks.disengage(operator="Abdul Hayy")
    assert ks.is_engaged() is False
