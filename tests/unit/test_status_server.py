import json
import threading
import urllib.request
from collections.abc import Generator
from pathlib import Path

import pytest

from ops.status_server import create_status_server
from src.connector.server import AegisConnectorServer
from src.storage.db import Database


@pytest.fixture
def running_status_server(tmp_path: Path) -> Generator[str, None, None]:
    db = Database(db_path=tmp_path / "status_test.db")
    server_connector = AegisConnectorServer(mode="PAPER", db=db)
    server_connector.seed_mock_data()

    http_server = create_status_server(host="127.0.0.1", port=18088, connector=server_connector, db=db)
    t = threading.Thread(target=http_server.serve_forever, daemon=True)
    t.start()
    yield "http://127.0.0.1:18088"
    http_server.shutdown()


def test_status_server_health_and_status(running_status_server: str) -> None:
    # 1. Health check
    with urllib.request.urlopen(f"{running_status_server}/health", timeout=3) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode())
        assert data["status"] == "HEALTHY"

    # 2. Status check
    with urllib.request.urlopen(f"{running_status_server}/status", timeout=3) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode())
        assert data["mode"] == "PAPER"
        assert "equity" in data

    # 3. Report check
    with urllib.request.urlopen(f"{running_status_server}/report", timeout=3) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode())
        assert "total_trades" in data
