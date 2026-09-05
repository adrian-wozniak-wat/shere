import os
import time
import logging
from django.utils import timezone
from django.db import transaction
from django.conf import settings

from emotion_analyzer.models import (
    HomeAssistantCredentials,
    Camera,
    Entity,
    PollCycle,
    EntityStatus,
    CameraSnapshot,
)
from emotion_analyzer.services.analyze_emotion import (
    save_camera_snapshot,
    analyze_emotion,
)
from emotion_analyzer.services.get_entity_data import get_entity_data

logger = logging.getLogger(__name__)

def poll_ha_data():
    """
    Polls Home Assistant data by fetching all registered cameras and entities.
    
    1. Gets from database objects: ha_credentials, list of all cameras, list of all entities.
    2. For each camera it uses analyze_emotion function.
    3. For each entity it uses get_entity_data.
    4. Based on data returned it creates a new PollCycle object with EntityStatuses and CameraSnapshots.
    
    Returns:
        PollCycle: The created PollCycle instance, or None if credentials are missing.
    """
    start_time = time.perf_counter()

    # 1. Gets from database objects
    ha_credentials = HomeAssistantCredentials.objects.first()
    if not ha_credentials:
        logger.warning("No Home Assistant Credentials found in the database. Polling skipped.")
        return None

    cameras = list(Camera.objects.all())
    entities = list(Entity.objects.all())

    # Build HA Url and retrieve token
    ha_url = f"http://{ha_credentials.host}:{ha_credentials.port}"
    token = ha_credentials.token

    now = timezone.now()
    base_timestamp = int(now.timestamp())
    year_month_day = now.strftime('%Y/%m/%d')

    media_root = getattr(settings, 'MEDIA_ROOT', os.path.join(settings.BASE_DIR, 'media'))
    files_directory = os.path.join(media_root, 'camera_snapshots', year_month_day)

    total_face_ms = 0
    total_emotion_ms = 0
    any_face_run = False
    any_emotion_run = False

    # Use a transaction block to ensure all status and snapshot records are created together
    with transaction.atomic():
        poll_cycle = PollCycle.objects.create()

        # 2. For each camera, fetch and save snapshot, then analyze emotion
        for camera in cameras:
            # Avoid filename collisions when polling multiple cameras concurrently
            camera_timestamp = f"{base_timestamp}_{camera.camera_id}"
            
            image_path = save_camera_snapshot(
                ha_url=ha_url,
                camera_entity=camera.camera_id,
                files_directory=files_directory,
                timestamp=camera_timestamp,
                token=token
            )
            
            emotion, confidence, face_ms, emotion_ms = None, None, None, None
            if image_path:
                emotion, confidence, face_ms, emotion_ms = analyze_emotion(image_path)
            
            if face_ms is not None:
                total_face_ms += face_ms
                any_face_run = True
            if emotion_ms is not None:
                total_emotion_ms += emotion_ms
                any_emotion_run = True

            # Check if the snapshot image was successfully written to the media directory
            image_field_val = None
            if image_path and os.path.exists(image_path):
                image_field_val = os.path.relpath(image_path, media_root)

            CameraSnapshot.objects.create(
                poll_cycle=poll_cycle,
                camera=camera,
                image=image_field_val,
                detected_emotion=emotion,
                confidence_score=confidence,
                face_recognition_milliseconds=face_ms,
                emotion_recognition_milliseconds=emotion_ms
            )

        # 3. For each entity, use get_entity_data
        for entity in entities:
            state, attributes = get_entity_data(
                ha_url=ha_url,
                token=token,
                entity_id=entity.entity_id
            )
            
            # If the retrieval fails, default the state value to 'unknown'
            state_value = state if state is not None else "unknown"
            
            EntityStatus.objects.create(
                poll_cycle=poll_cycle,
                entity=entity,
                state_value=state_value
            )

        end_time = time.perf_counter()
        cycle_length_ms = int(round((end_time - start_time) * 1000))

        poll_cycle.cycle_length_milliseconds = cycle_length_ms
        poll_cycle.face_recognition_milliseconds = total_face_ms if any_face_run else None
        poll_cycle.emotion_recognition_milliseconds = total_emotion_ms if any_emotion_run else None
        poll_cycle.save()

        return poll_cycle
