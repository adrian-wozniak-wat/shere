#!/usr/bin/env python3
import os
import sys
import csv
import django

# Set up paths and Django environment
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
SRC_DIR = os.path.join(PROJECT_ROOT, "src")

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.contrib.auth import get_user_model
from emotion_analyzer.models import HomeAssistantCredentials, Entity, Camera

CSV_PATH = os.path.join(SCRIPT_DIR, "sensor_data.csv")


def derive_location(friendly_name, entity_id):
    if not friendly_name:
        return "Living Room"
    fname = friendly_name.lower()
    if "living room" in fname:
        return "Living Room"
    elif "indoor" in fname or "air quality" in fname:
        return "Indoor"
    elif "main power" in fname or "power meter" in fname:
        return "Main Panel"
    return "Living Room"


def initialize_db():
    print("[InitDB] Starting database initialization for mock HA environment...")

    # 1. Initialize Superuser if APP_USER & APP_PASS are set
    User = get_user_model()
    app_user = os.getenv('APP_USER', 'admin')
    app_pass = os.getenv('APP_PASS', 'admin123')
    if app_user and app_pass:
        user_obj, created = User.objects.get_or_create(username=app_user, defaults={'is_superuser': True, 'is_staff': True})
        if created:
            user_obj.set_password(app_pass)
            user_obj.save()
            print(f"[InitDB] Superuser '{app_user}' created successfully.")
        else:
            print(f"[InitDB] Superuser '{app_user}' already exists.")
    else:
        user_obj = User.objects.first()

    # 2. Setup Home Assistant Credentials
    if not user_obj:
        user_obj = User.objects.create_user(username="default_user", password="password123")

    creds = HomeAssistantCredentials.objects.first()
    if not creds:
        creds = HomeAssistantCredentials(user=user_obj)

    creds.username = app_user
    creds.host = "127.0.0.1"
    creds.port = int(os.environ.get("MOCK_HA_PORT", 8123))
    creds.token = "mock_token"
    creds.save()
    print(f"[InitDB] HomeAssistantCredentials set to http://{creds.host}:{creds.port}")

    # 3. Import unique entities from sensor_data.csv
    if os.path.exists(CSV_PATH):
        unique_entities = {}
        with open(CSV_PATH, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                eid = row.get("entity_id", "").strip()
                if eid and eid not in unique_entities:
                    unique_entities[eid] = {
                        "friendly_name": row.get("friendly_name", "").strip(),
                        "unit_of_measurement": row.get("unit_of_measurement", "").strip() or None
                    }

        for eid, info in unique_entities.items():
            location = derive_location(info["friendly_name"], eid)
            entity_obj, created = Entity.objects.update_or_create(
                entity_id=eid,
                defaults={
                    "name": info["friendly_name"],
                    "location": location,
                    "unit_of_measurement": info["unit_of_measurement"]
                }
            )
            action = "Created" if created else "Updated"
            print(f"[InitDB] {action} Entity: {entity_obj.entity_id} ({entity_obj.name})")
    else:
        print(f"[InitDB] Warning: CSV file not found at {CSV_PATH}")

    # 4. Initialize mock_camera
    camera_obj, created = Camera.objects.update_or_create(
        camera_id="mock_camera",
        defaults={
            "name": "Mock Camera",
            "location": "Living Room"
        }
    )
    action = "Created" if created else "Updated"
    print(f"[InitDB] {action} Camera: {camera_obj.camera_id} ({camera_obj.name})")

    print("[InitDB] Database initialization completed successfully.")


if __name__ == "__main__":
    initialize_db()
