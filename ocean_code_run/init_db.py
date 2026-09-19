#!/usr/bin/env python3
import os
import sys
import csv

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
CSV_PATH = os.path.join(SCRIPT_DIR, "sensor_data.csv")
DB_PATH = os.path.join(SCRIPT_DIR, "db.sqlite3")

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ.setdefault("DB_ENGINE", "django.db.backends.sqlite3")
os.environ.setdefault("DB_NAME", DB_PATH)

import django
django.setup()

from django.core.management import call_command
from django.contrib.auth import get_user_model
from django_celery_beat.models import PeriodicTask, IntervalSchedule
from emotion_analyzer.models import HomeAssistantCredentials, Camera, Entity


def init_db():
    print(f"[InitDB] Running database migrations on '{os.environ.get('DB_NAME')}'...")
    call_command("migrate", interactive=False)

    User = get_user_model()
    username = os.environ.get("APP_USER", "admin")
    password = os.environ.get("APP_PASS", "admin123")

    user, created = User.objects.get_or_create(
        username=username,
        defaults={"is_superuser": True, "is_staff": True}
    )
    if created:
        user.set_password(password)
        user.save()
        print(f"[InitDB] Created superuser '{username}'.")
    else:
        print(f"[InitDB] Superuser '{username}' already exists.")

    port = int(os.environ.get("MOCK_HA_PORT", 8123))
    cred = HomeAssistantCredentials.objects.first()
    if not cred:
        cred = HomeAssistantCredentials(user=user, username=username, host="127.0.0.1", port=port)
        cred.token = "mock_token"
        cred.save()
        print(f"[InitDB] Created HomeAssistantCredentials (127.0.0.1:{port}).")
    else:
        cred.host = "127.0.0.1"
        cred.port = port
        cred.save()

    if not Camera.objects.filter(camera_id="camera.ocean_cam").exists():
        Camera.objects.create(
            camera_id="camera.ocean_cam",
            name="Ocean Living Room Cam",
            location="Living Room"
        )
        print("[InitDB] Created mock Camera 'camera.ocean_cam'.")

    # Read sensor_data.csv and seed matching entities
    if os.path.exists(CSV_PATH):
        print(f"[InitDB] Reading and seeding entities from {CSV_PATH}...")
        seen_entities = set()
        with open(CSV_PATH, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                eid = row.get("entity_id", "").strip()
                if eid and eid not in seen_entities:
                    seen_entities.add(eid)
                    name = row.get("friendly_name", eid)
                    unit = row.get("unit_of_measurement", "")

                    location = "Living Room"
                    if "utility" in name.lower() or "power" in eid.lower():
                        location = "Utility Room"
                    elif "outdoor" in name.lower():
                        location = "Outdoors"

                    entity, ent_created = Entity.objects.get_or_create(
                        entity_id=eid,
                        defaults={
                            "name": name,
                            "location": location,
                            "unit_of_measurement": unit
                        }
                    )
                    if ent_created:
                        print(f"[InitDB] Created Entity: {eid} ({name})")
                    else:
                        entity.name = name
                        entity.unit_of_measurement = unit
                        entity.save()
                        print(f"[InitDB] Updated Entity: {eid} ({name})")
    else:
        print(f"[InitDB] Warning: {CSV_PATH} not found.")

    # Initialize default GUI PeriodicTask setting if not present
    task_name = 'Analyze Emotions Periodic Task'
    if not PeriodicTask.objects.filter(name=task_name).exists():
        schedule, _ = IntervalSchedule.objects.get_or_create(every=5, period='seconds')
        PeriodicTask.objects.create(
            name=task_name,
            interval=schedule,
            task='emotion_analyzer.tasks.analyze_emotions',
            enabled=True
        )
        print(f"[InitDB] Created default PeriodicTask '{task_name}' (Enabled, 5s interval).")

    print("[InitDB] Database initialization successfully completed!")


if __name__ == "__main__":
    init_db()
