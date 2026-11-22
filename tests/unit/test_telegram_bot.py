
from pathlib import Path

import pytest

from ops.telegram_bot import TelegramCommandHandler
from src.connector.server import AegisConnectorServer
from src.gate.kill_switch import StandaloneKillSwitch


def test_telegram_unauthorized_user_blocked() -> None:
    server = AegisConnectorServer(mode="PAPER")
    handler = TelegramCommandHandler(server=server, authorized_chat_id="12345678")

    # Unauthorized user tries to kill
    response = handler.handle_command(user_chat_id="99999999", command_text="/kill")
    assert "Unauthorized" in response
    assert server.kill_switch_active is False


def test_telegram_status_command() -> None:
    server = AegisConnectorServer(mode="PAPER")
    server.seed_mock_data()
    handler = TelegramCommandHandler(server=server, authorized_chat_id="12345678")

    response = handler.handle_command(user_chat_id="12345678", command_text="/status")
    assert "AEGIS SYSTEM STATUS" in response
    assert "PAPER" in response
    assert "$10000.00" in response


def test_telegram_emergency_kill_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mock_token = "mock_tg_token_123"  # gitleaks:allow
    monkeypatch.setenv("AEGIS_OWNER_SECRET", mock_token)
    server = AegisConnectorServer(mode="PAPER")
    lock_file = tmp_path / "tg_kill.lock"
    ks = StandaloneKillSwitch(lock_file_path=lock_file)
    handler = TelegramCommandHandler(server=server, authorized_chat_id="12345678", kill_switch=ks)

    response = handler.handle_command(user_chat_id="12345678", command_text="/kill Emergency stop via chat")
    assert "EMERGENCY KILL SWITCH ENGAGED" in response
    assert handler.kill_switch.is_engaged() is True

    # Cleanup kill switch
    handler.kill_switch.disengage(operator="Abdul Hayy Khan", token=mock_token)
    assert handler.kill_switch.is_engaged() is False


def test_telegram_approve_proposal_command(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_token = "mock_tg_token_456"  # gitleaks:allow
    monkeypatch.setenv("AEGIS_OWNER_SECRET", mock_token)
    server = AegisConnectorServer(mode="LIVE_WITH_APPROVAL")
    server.seed_mock_data()
    handler = TelegramCommandHandler(server=server, authorized_chat_id="12345678")

    prop = server.submit_proposal({
        "symbol": "BTC/USDT",
        "side": "BUY",
        "order_type": "LIMIT",
        "price": "30000.00",
        "size": "0.01",
        "stop_loss": "29000.00",
        "rationale_id": "TG_TEST"
    })
    p_id = prop["proposal_id"]

    response = handler.handle_command(user_chat_id="12345678", command_text=f"/approve {p_id}")
    assert "APPROVED & FILLED" in response
