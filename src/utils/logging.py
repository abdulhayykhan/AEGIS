"""AEGIS Structured JSON Logging and Audit Tracing.

Built by [Abdul Hayy Khan](https://abdulhayykhan.dev).
Citations:
- AEGIS Project Review Report (Section 6.2: Machine-Readable JSON Telemetry)
"""

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any


class AegisJsonFormatter(logging.Formatter):
    """Structured JSON logging formatter compliant with enterprise observability and audit trails."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        # Add custom extra attributes if present
        for key in ("component", "run_id", "trace_id", "symbol", "proposal_id", "order_id"):
            if hasattr(record, key):
                log_obj[key] = getattr(record, key)

        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj, default=str)


def get_logger(name: str = "aegis") -> logging.Logger:
    """Return a configured logger with structured JSON output."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(AegisJsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger
