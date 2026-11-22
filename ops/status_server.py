"""AEGIS Telemetry & Status HTTP Server.

Built by [Abdul Hayy Khan](https://abdulhayykhan.dev).
Citations:
- AEGIS Project Review Report (Section 6.3: Health & Metrics Endpoint)
"""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from ops.weekly_report import generate_weekly_report
from src.connector.server import AegisConnectorServer
from src.gate.kill_switch import StandaloneKillSwitch
from src.storage.db import Database


class AegisStatusHandler(BaseHTTPRequestHandler):
    """HTTP Request Handler exposing read-only operational telemetry and governance health."""

    server_connector: AegisConnectorServer | None = None
    db: Database | None = None

    def _send_json_response(self, status_code: int, data: dict[str, Any]) -> None:
        payload = json.dumps(data, default=str).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        path = self.path.split("?")[0].rstrip("/")

        if path in ("", "/health"):
            ks = StandaloneKillSwitch().is_engaged()
            self._send_json_response(200, {
                "status": "HEALTHY",
                "kill_switch_engaged": ks,
                "service": "AEGIS Operational Status API"
            })
        elif path == "/status":
            connector = self.server_connector or AegisConnectorServer(mode="PAPER", db=self.db)
            acc = connector.get_account()
            run_state = connector.get_run_state()
            self._send_json_response(200, {
                "mode": connector.mode,
                "equity": acc.get("equity", "0.00"),
                "cash": acc.get("cash", "0.00"),
                "daily_realized_loss": run_state.get("daily_realized_loss", "0.00"),
                "max_orders_per_day": run_state.get("max_orders_per_day", 10),
                "orders_today_count": run_state.get("orders_today_count", 0),
                "kill_switch_active": run_state.get("kill_switch_active", False)
            })
        elif path == "/positions":
            connector = self.server_connector or AegisConnectorServer(mode="PAPER", db=self.db)
            acc = connector.get_account()
            self._send_json_response(200, {
                "positions": acc.get("positions", {})
            })
        elif path == "/report":
            db = self.db or Database()
            report = generate_weekly_report(db)
            self._send_json_response(200, report.model_dump())
        else:
            self._send_json_response(404, {"error": f"Endpoint '{path}' not found."})

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default stdout web request logging to keep logs clean."""


def create_status_server(
    host: str = "127.0.0.1",
    port: int = 8080,
    connector: AegisConnectorServer | None = None,
    db: Database | None = None
) -> HTTPServer:
    """Create and return configured status HTTP server."""
    AegisStatusHandler.server_connector = connector
    AegisStatusHandler.db = db or (connector.db if connector else Database())
    return HTTPServer((host, port), AegisStatusHandler)
