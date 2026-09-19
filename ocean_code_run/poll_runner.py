#!/usr/bin/env python3
import os
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
SRC_DIR = os.path.join(PROJECT_ROOT, "src")

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logging.getLogger('emotion_analyzer').setLevel(logging.INFO)

from django_celery_beat.models import PeriodicTask
from emotion_analyzer.services.poll_ha_data import poll_ha_data


TASK_NAME = 'Analyze Emotions Periodic Task'


def get_task_config():
    """
    Reads the PeriodicTask configuration set by the user in the Django GUI.
    Returns:
        tuple: (is_enabled, interval_seconds)
    """
    try:
        task = PeriodicTask.objects.filter(name=TASK_NAME).first()
        if not task:
            return False, 5.0

        is_enabled = task.enabled
        if not task.interval:
            return is_enabled, 5.0

        every = task.interval.every or 5
        period = task.interval.period or 'seconds'

        multiplier = 1.0
        if period == 'minutes':
            multiplier = 60.0
        elif period == 'hours':
            multiplier = 3600.0
        elif period == 'days':
            multiplier = 86400.0

        interval_seconds = max(1.0, float(every * multiplier))
        return is_enabled, interval_seconds
    except Exception as e:
        print(f"[PollRunner] Error reading task config from DB: {e}")
        return False, 5.0


def run_loop():
    print(f"[PollRunner] Polling cycle process initialized. Monitoring GUI settings for '{TASK_NAME}'...")

    last_poll_time = 0.0
    was_enabled = None
    last_interval = None

    while True:
        is_enabled, interval_seconds = get_task_config()

        if is_enabled != was_enabled or interval_seconds != last_interval:
            status_str = "ENABLED" if is_enabled else "DISABLED/STOPPED"
            print(f"[PollRunner] GUI setting detected -> State: {status_str} | Interval: {interval_seconds}s")
            was_enabled = is_enabled
            last_interval = interval_seconds

        if is_enabled:
            now = time.time()
            if now - last_poll_time >= interval_seconds:
                try:
                    poll_cycle = poll_ha_data()
                    if poll_cycle:
                        print(f"[PollRunner] Created PollCycle ID: {poll_cycle.id} (Interval: {interval_seconds}s)")
                    else:
                        print("[PollRunner] Poll cycle skipped (no credentials or devices).")
                except Exception as e:
                    print(f"[PollRunner] Error during poll cycle: {e}")
                last_poll_time = time.time()

        # Responsive sleep tick checking GUI DB state every 1 second
        time.sleep(1.0)


if __name__ == "__main__":
    run_loop()
