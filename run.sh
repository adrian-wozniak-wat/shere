#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "Starting entrypoint script..."

# Export PYTHONPATH to include src directory so python/celery can locate modules/config
export PYTHONPATH=src

# Check the first argument passed to the script
case "$1" in
    web)
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
        echo "Starting Celery Worker..."
        exec celery -A config worker --loglevel=info
        ;;
    beat)
        echo "Starting Celery Beat..."
        exec celery -A config beat --loglevel=info
        ;;
    *)
        echo "Error: Invalid argument '$1'. Must be one of: web, worker, beat"
        exit 1
        ;;
esac