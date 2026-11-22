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


def test_kill_switch_disengagement_by_owner(temp_kill_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that only authorized owner disengagement with valid token can clear the kill switch."""
    secret = "owner_secret_key_789"
    monkeypatch.setenv("AEGIS_OWNER_SECRET", secret)
    ks = StandaloneKillSwitch(lock_file_path=temp_kill_file)
    ks.engage(reason="Test", operator="Abdul Hayy")
    assert ks.is_engaged() is True

    # Agent cannot clear it; only authorized operator
    with pytest.raises(PermissionError, match="Unauthorized"):
        ks.disengage(operator="AI_AGENT", token=secret)

    # Authorized owner disengages with valid token
    ks.disengage(operator="Abdul Hayy", token=secret)
    assert ks.is_engaged() is False
