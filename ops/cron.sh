#!/usr/bin/env bash
# ==============================================================================
# AEGIS Scheduled Runner Script (Cron / Systemd)
# Runs at the close of every 4-hour bar (00:00, 04:00, 08:00, 12:00, 16:00, 20:00 UTC)
# ==============================================================================

set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APP_DIR"

LOG_DIR="$APP_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/aegis_$(date +'%Y%m%d').log"

echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] Starting scheduled AEGIS trading cycle..." >> "$LOG_FILE"

# Activate virtual environment if present
if [ -d "$APP_DIR/.venv" ]; then
    source "$APP_DIR/.venv/bin/activate"
fi

# Run cycle with configured mode
MODE="${AEGIS_EXECUTION_MODE:-PAPER_EXECUTION}"
aegis run --mode "$MODE" >> "$LOG_FILE" 2>&1

EXIT_CODE=$?
echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] Cycle completed with exit code: $EXIT_CODE" >> "$LOG_FILE"

exit $EXIT_CODE
