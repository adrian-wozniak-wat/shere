"""
Integration test for the ``analyze_emotions`` Celery task.

It spins up:
  * a throw-away PostgreSQL docker container (``postgres:16``),
  * the mock Home Assistant HTTP server from ``ha_mock_run_config/mock_ha.py``,
and seeds the DB with ``ha_mock_run_config/initialize_db.py``.
Then it runs the task synchronously and verifies the created records.

Run with:
    pytest test/integration/test_analyze_emotions_task.py -s
Requirements: docker CLI available and dev requirements installed:
    pip install -r requirements-dev.txt
"""
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import uuid

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
MOCK_DIR = os.path.join(PROJECT_ROOT, "ha_mock_run_config")
for p in (SRC_DIR, MOCK_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

PG_IMAGE = os.environ.get("TEST_PG_IMAGE", "postgres:16")
DB_NAME, DB_USER, DB_PASSWORD = "ha_emotion_test", "test", "test"


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_postgres(container, timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = subprocess.run(
            ["docker", "exec", container, "pg_isready", "-U", DB_USER, "-d", DB_NAME],
            capture_output=True,
        )
        if r.returncode == 0:
            time.sleep(1)  # pg_isready may succeed slightly before init completes
            return
        time.sleep(1)
    raise RuntimeError("PostgreSQL container did not become ready in time")


@pytest.fixture(scope="session")
def postgres_container():
    if shutil.which("docker") is None:
        pytest.skip("docker CLI not available")
    name = f"ha_emotion_test_pg_{uuid.uuid4().hex[:8]}"
    port = _free_port()
    subprocess.run(
        [
            "docker", "run", "-d", "--rm", "--name", name,
            "-e", f"POSTGRES_DB={DB_NAME}",
            "-e", f"POSTGRES_USER={DB_USER}",
            "-e", f"POSTGRES_PASSWORD={DB_PASSWORD}",
            "-p", f"127.0.0.1:{port}:5432",
            PG_IMAGE,
        ],
        check=True,
        capture_output=True,
    )
    try:
        _wait_for_postgres(name)
        yield {"host": "127.0.0.1", "port": port}
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)


@pytest.fixture(scope="session")
def mock_ha_server():
    import mock_ha

    # Always serve a photo with a clearly visible face so emotion
    # recognition is deterministic (the mock photos also contain a landscape).
    face_photo = os.path.join(mock_ha.PHOTOS_DIR, "Keanu_Reeves.jpg")
    mock_ha.MockHAHandler.get_random_photo = classmethod(
        lambda cls: (face_photo, "image/jpeg")
    )

    port = _free_port()
    server = mock_ha.ThreadedHTTPServer(("127.0.0.1", port), mock_ha.MockHAHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield port
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture(scope="session")
def django_env(postgres_container, mock_ha_server):
    media_root = tempfile.mkdtemp(prefix="ha_emotion_media_")
    os.environ.update({
        "DJANGO_SETTINGS_MODULE": "config.settings",
        "DB_ENGINE": "django.db.backends.postgresql",
        "DB_NAME": DB_NAME,
        "DB_USER": DB_USER,
        "DB_PASSWORD": DB_PASSWORD,
        "DB_HOST": postgres_container["host"],
        "DB_PORT": str(postgres_container["port"]),
        "MOCK_HA_PORT": str(mock_ha_server),
    })

    import django
    from django.conf import settings

    django.setup()
    settings.MEDIA_ROOT = media_root

    from django.core.management import call_command
    call_command("migrate", interactive=False, verbosity=0)

    import initialize_db
    initialize_db.initialize_db()

    try:
        yield media_root
    finally:
        shutil.rmtree(media_root, ignore_errors=True)


def test_analyze_emotions_task_with_mock_ha(django_env):
    from emotion_analyzer.models import (
        Camera, CameraSnapshot, Entity, EntityStatus, PollCycle,
    )
    from emotion_analyzer.tasks import analyze_emotions

    assert Camera.objects.filter(camera_id="mock_camera").exists()
    entity_count = Entity.objects.count()
    assert entity_count > 0
    cycles_before = PollCycle.objects.count()

    # Run the Celery task synchronously (no broker needed).
    result = analyze_emotions.apply().get()

    assert result.startswith("Success: Polling cycle ID")
    assert PollCycle.objects.count() == cycles_before + 1

    cycle = PollCycle.objects.order_by("-id").first()
    assert str(cycle.id) in result
    assert cycle.cycle_length_milliseconds is not None

    # Entities: one status per entity, values come from the mock CSV.
    statuses = EntityStatus.objects.filter(poll_cycle=cycle)
    assert statuses.count() == entity_count
    assert all(s.state_value != "unknown" for s in statuses)

    # Camera: snapshot was fetched from mock HA and saved to MEDIA_ROOT.
    snapshots = CameraSnapshot.objects.filter(poll_cycle=cycle)
    assert snapshots.count() == 1
    snap = snapshots.first()
    assert snap.image, "Snapshot image was not saved"
    assert os.path.exists(os.path.join(django_env, snap.image.name))

    # A face photo is always served, so emotion recognition must succeed.
    assert snap.detected_emotion, "Emotion was not detected"
    assert snap.confidence_score is not None
    assert 0.0 <= snap.confidence_score <= 1.0
    assert snap.emotion_recognition_milliseconds is not None
