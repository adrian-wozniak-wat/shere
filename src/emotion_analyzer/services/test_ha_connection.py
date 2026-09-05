import cv2
import requests
import numpy as np

from emotion_analyzer.models import HomeAssistantCredentials, Camera, Entity
from emotion_analyzer.services.get_entity_data import get_entity_data
from emotion_analyzer.services.analyze_emotion import analyze_emotion


def test_ha_connection():
    """
    Tests the connection to Home Assistant, checks if camera and entity data
    can be successfully polled, and verifies that the emotion recognition model works.
    This function performs no database writes and does not save any files.

    Returns:
        str: A string describing the failure (which part failed and why), or None if successful.
    """
    # 1. Retrieve credentials
    try:
        ha_credentials = HomeAssistantCredentials.objects.first()
    except Exception as e:
        return f"Failed to query database for credentials: {e}"

    if not ha_credentials:
        return "Failed to retrieve Home Assistant credentials: No credentials found in database."

    # 2. Build Home Assistant URL and headers
    ha_url = f"http://{ha_credentials.host}:{ha_credentials.port}"
    token = ha_credentials.token
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    # 3. Test general connectivity to Home Assistant API
    try:
        response = requests.get(f"{ha_url}/api/", headers=headers, timeout=10)
        response.raise_for_status()
    except Exception as e:
        return f"Failed to connect to Home Assistant API at {ha_url}: {e}"

    # 4. Check entity data polling
    try:
        entities = list(Entity.objects.all())
    except Exception as e:
        return f"Failed to query database for entities: {e}"

    for entity in entities:
        try:
            state, attributes = get_entity_data(ha_url, token, entity.entity_id)
            if state is None:
                return f"Failed to poll entity data for {entity.entity_id}: Received empty state."
        except Exception as e:
            return f"Failed to poll entity data for {entity.entity_id}: {e}"

    # 5. Check camera polling and emotion recognition model
    try:
        cameras = list(Camera.objects.all())
    except Exception as e:
        return f"Failed to query database for cameras: {e}"

    if cameras:
        for camera in cameras:
            # Fetch snapshot from camera proxy
            try:
                proxy_url = f"{ha_url}/api/camera_proxy/{camera.camera_id}"
                response = requests.get(proxy_url, headers=headers, timeout=10)
                response.raise_for_status()
            except Exception as e:
                # Query HA state to provide a clearer explanation if the camera is unavailable/offline
                try:
                    state_url = f"{ha_url}/api/states/{camera.camera_id}"
                    state_resp = requests.get(state_url, headers=headers, timeout=5)
                    if state_resp.status_code == 200:
                        state_data = state_resp.json()
                        if state_data.get("state") == "unavailable":
                            return f"Camera {camera.camera_id} is unavailable in Home Assistant (state is 'unavailable'). Please verify that the camera is powered on and active in Home Assistant."
                except Exception:
                    pass
                return f"Failed to poll camera snapshot for {camera.camera_id}: {e}"

            # Decode the image in-memory
            try:
                image_bytes = np.frombuffer(response.content, dtype=np.uint8)
                frame = cv2.imdecode(image_bytes, cv2.IMREAD_COLOR)
                if frame is None:
                    return f"Failed to decode camera snapshot for {camera.camera_id}."
            except Exception as e:
                return f"Failed to decode camera snapshot for {camera.camera_id}: {e}"

            # Run emotion recognition model in-memory
            try:
                emotion, score, *rest = analyze_emotion(frame)
                if emotion is None:
                    return f"Failed to run emotion recognition: model returned empty analysis for {camera.camera_id}."
            except Exception as e:
                return f"Failed to run emotion recognition model on {camera.camera_id}: {e}"
    else:
        # If no cameras are configured, test emotion model with a dummy in-memory image
        try:
            dummy_frame = np.zeros((100, 100, 3), dtype=np.uint8)
            emotion, score, *rest = analyze_emotion(dummy_frame)
            if emotion is None:
                return "Failed to run emotion recognition model: model returned empty analysis."
        except Exception as e:
            return f"Failed to run emotion recognition model: {e}"

    return None
