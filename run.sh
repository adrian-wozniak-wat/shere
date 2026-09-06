#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "Starting entrypoint script..."

# Export PYTHONPATH to include src directory so python/celery can locate modules/config
export PYTHONPATH=src

wait_for_db() {
    echo "Waiting for PostgreSQL database to be ready..."
    python -c "
import time, os, psycopg2
db_user = os.getenv('DB_USER', 'admin')
db_pass = os.getenv('DB_PASSWORD', 'admin123')
db_host = os.getenv('DB_HOST', '127.0.0.1')
for i in range(30):
    try:
        conn = psycopg2.connect(dbname='ha_emotion_research', user=db_user, password=db_pass, host=db_host)
        conn.close()
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

# Check the first argument passed to the script
case "$1" in
    web)
        wait_for_db
        echo "Running Django Database Migrations..."
        python src/manage.py migrate --noinput
        echo "Creating superuser if needed..."
        python src/manage.py shell -c "
import os
from django.contrib.auth import get_user_model
User = get_user_model()
username = os.getenv('APP_USER')
password = os.getenv('APP_PASS')
if username and password:
    if not User.objects.filter(username=username).exists():
        User.objects.create_superuser(username=username, password=password, email='')
        print('Superuser created successfully.')
    else:
        print('Superuser already exists.')
else:
    print('APP_USER or APP_PASS environment variables not set. Skipping.')
"
        echo "Starting Django Development Server..."
        exec python src/manage.py runserver 0.0.0.0:8000
        ;;
    worker)
        wait_for_db
        echo "Starting Celery Worker..."
        exec celery -A config worker --loglevel=info --concurrency=${CELERY_WORKER_CONCURRENCY:-2}
        ;;
    beat)
        wait_for_db
        echo "Starting Celery Beat..."
        exec celery -A config beat --loglevel=info
        ;;
    *)
        echo "Error: Invalid argument '$1'. Must be one of: web, worker, beat"
        exit 1
        ;;
esac