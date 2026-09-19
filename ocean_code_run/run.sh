#!/bin/bash

# Exit immediately if a command fails
set -e

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)
DB_PATH="$SCRIPT_DIR/db.sqlite3"

# Detect python executable
if [ -f "$PROJECT_ROOT/.venv3.12/bin/python" ]; then
    PYTHON_CMD="$PROJECT_ROOT/.venv3.12/bin/python"
elif [ -f "$PROJECT_ROOT/.venv/bin/python" ]; then
    PYTHON_CMD="$PROJECT_ROOT/.venv/bin/python"
elif command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
    PYTHON_CMD="python"
else
    echo "Error: Python executable not found."
    exit 1
fi

echo "=========================================================="
echo "Starting Standalone Offline Mode (ocean_code_run)..."
echo "=========================================================="
echo "Project Root: $PROJECT_ROOT"
echo "Python:       $PYTHON_CMD"
echo "SQLite DB:    $DB_PATH"
echo "Models Cache: $SCRIPT_DIR/models_cache"
echo "=========================================================="

export PYTHONPATH="$PROJECT_ROOT/src:$SCRIPT_DIR"
export DB_ENGINE="django.db.backends.sqlite3"
export DB_NAME="$DB_PATH"
export MOCK_HA_PORT="${MOCK_HA_PORT:-8123}"
export CELERY_BROKER_URL="memory://"
export APP_USER="${APP_USER:-admin}"
export APP_PASS="${APP_PASS:-admin123}"

# Configure strict offline mode for Hugging Face and Transformers models
export HF_HOME="${HF_HOME:-$SCRIPT_DIR/models_cache}"
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1

echo "Verifying local ML models cache..."
"$PYTHON_CMD" "$SCRIPT_DIR/bundle_models.py"

echo "Initializing database and seeding sensor entities..."
"$PYTHON_CMD" "$SCRIPT_DIR/init_db.py"

echo "Starting Mock Home Assistant Server on port $MOCK_HA_PORT..."
"$PYTHON_CMD" "$SCRIPT_DIR/mock_ha_server.py" &
MOCK_HA_PID=$!

echo "Starting Standalone Poll Cycle Process..."
"$PYTHON_CMD" "$SCRIPT_DIR/poll_runner.py" &
POLL_PID=$!

cleanup() {
    echo ""
    echo "Shutting down offline processes (Mock HA server PID $MOCK_HA_PID, Poll Runner PID $POLL_PID)..."
    kill $MOCK_HA_PID $POLL_PID 2>/dev/null || true
}
trap cleanup EXIT SIGINT SIGTERM

echo "Starting Django Development Server on 0.0.0.0:8000..."
"$PYTHON_CMD" "$PROJECT_ROOT/src/manage.py" runserver 0.0.0.0:8000
