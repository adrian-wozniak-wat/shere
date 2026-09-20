#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "Starting MOCK_HA worker entrypoint script..."

export PYTHONPATH=src

wait_for_db() {
    echo "Waiting for database to be ready..."
    python -c "
import time, os, django, sys
sys.path.insert(0, 'src')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
for i in range(30):
    try:
        django.setup()
        from django.db import connection
        connection.ensure_connection()
        print('Database connection established successfully.')
        break
    except Exception as e:
        print(f'Waiting for database ({e})...')
        time.sleep(2)
else:
    print('Database connection timed out.')
    exit(1)
"
}

wait_for_db

echo "Running Django Database Migrations..."
python src/manage.py migrate --noinput

echo "Initializing database with MOCK_HA data..."
python ha_mock_run_config/initialize_db.py

echo "Starting Mock Home Assistant server in background..."
python ha_mock_run_config/mock_ha.py &
MOCK_HA_PID=$!
sleep 1

echo "Starting Celery Worker..."
exec celery -A config worker --loglevel=info --concurrency=${CELERY_WORKER_CONCURRENCY:-2}
