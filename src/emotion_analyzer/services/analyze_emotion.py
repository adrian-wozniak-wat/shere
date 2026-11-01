import os
import cv2
import requests
import numpy as np
import logging
import time

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Snapshot utilities
# ---------------------------------------------------------------------------

def save_camera_snapshot(ha_url, camera_entity, files_directory, timestamp, token):
    """
    Fetches a snapshot from a Home Assistant camera and saves it to a folder.

    Returns:
        str: The absolute path to the saved image file, or None if failed.
    """
    import datetime

    # Extract time components (hours, minutes, seconds) from the timestamp
    try:
        ts_part = str(timestamp).split('_')[0]
        ts_val = float(ts_part)
        dt = datetime.datetime.fromtimestamp(ts_val, tz=datetime.timezone.utc)
    except (ValueError, TypeError, IndexError):
        dt = datetime.datetime.now(datetime.timezone.utc)

    hours = dt.strftime('%H')
    minutes = dt.strftime('%M')
    seconds = dt.strftime('%S')

    # Ensure the directory exists with hours/minutes/seconds subdirectories
    target_directory = os.path.join(files_directory, hours, minutes, seconds)
    os.makedirs(target_directory, exist_ok=True)
    filename = os.path.join(target_directory, f"frame_{timestamp}.jpg")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    try:
        # Get the image snapshot directly from Home Assistant proxy
        # This bypasses the need for stream looping and gets the full-res capture
        proxy_url = f"{ha_url}/api/camera_proxy/{camera_entity}"
        response = requests.get(proxy_url, headers=headers, timeout=10)
        response.raise_for_status()

        # Convert bytes to an OpenCV image array
        image_bytes = np.frombuffer(response.content, dtype=np.uint8)
        frame = cv2.imdecode(image_bytes, cv2.IMREAD_COLOR)

        if frame is None:
            logger.error("Could not decode the image from Home Assistant.")
            return None

        # Save the image to the specified directory
        cv2.imwrite(filename, frame, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
        logger.info(f"Successfully saved snapshot to {filename}")
        return filename

    except Exception as e:
        logger.error(f"An error occurred while saving snapshot: {e}")
        return None


# ---------------------------------------------------------------------------
# Photo file retention policy
# ---------------------------------------------------------------------------

PHOTO_POLICY_ALL = "all"
PHOTO_POLICY_EMOTIONS = "emotions"
PHOTO_POLICY_NONE = "none"

_VALID_PHOTO_POLICIES = {PHOTO_POLICY_ALL, PHOTO_POLICY_EMOTIONS, PHOTO_POLICY_NONE}


def get_photo_file_policy() -> str:
    """Return the active PHOTO_FILE_POLICY ("all", "emotions" or "none")."""
    policy = os.environ.get("PHOTO_FILE_POLICY", PHOTO_POLICY_NONE).strip().lower()
    if policy not in _VALID_PHOTO_POLICIES:
        logger.warning(
            f"Unknown PHOTO_FILE_POLICY '{policy}'. Falling back to '{PHOTO_POLICY_NONE}'."
        )
        policy = PHOTO_POLICY_NONE
    return policy


def should_keep_photo(emotion_recognition_performed: bool) -> bool:
    """Decide whether snapshot files should be kept according to PHOTO_FILE_POLICY."""
    policy = get_photo_file_policy()
    if policy == PHOTO_POLICY_ALL:
        return True
    if policy == PHOTO_POLICY_EMOTIONS:
        return emotion_recognition_performed
    return False


def delete_snapshot_files(image_path):
    """Delete a snapshot file and its associated cropped face file (if any)."""
    if not image_path:
        return
    base, ext = os.path.splitext(image_path)
    for path in (image_path, f"{base}_face_cropped{ext}"):
        try:
            if os.path.exists(path):
                os.remove(path)
                logger.info(f"Removed snapshot file {path} (PHOTO_FILE_POLICY)")
        except OSError as e:
            logger.error(f"Could not remove snapshot file {path}: {e}")


# ---------------------------------------------------------------------------
# Model backend selection
# ---------------------------------------------------------------------------

# Supported backend identifiers
BACKEND_EMOTIEFFLIB = "emotiefflib"
BACKEND_DIMA = "dima"

_VALID_BACKENDS = {BACKEND_EMOTIEFFLIB, BACKEND_DIMA}


def _get_backend() -> str:
    """Return the active emotion model backend (normalised to lower-case)."""
    backend = os.environ.get("EMOTION_MODEL_BACKEND", BACKEND_EMOTIEFFLIB).strip().lower()
    if backend not in _VALID_BACKENDS:
        logger.warning(
            f"Unknown EMOTION_MODEL_BACKEND '{backend}'. "
            f"Falling back to '{BACKEND_EMOTIEFFLIB}'."
        )
        backend = BACKEND_EMOTIEFFLIB
    return backend


# ---------------------------------------------------------------------------
# EmotiEffLib backend (hse_face_emotion / HSEmotion)
# ---------------------------------------------------------------------------

_emotiefflib_recognizer = None


def _get_emotiefflib_recognizer():
    """Lazily initialise and cache the EmotiEffLib HSEmotionRecognizer."""
    global _emotiefflib_recognizer
    if _emotiefflib_recognizer is None:
        from emotiefflib.facial_analysis import EmotiEffLibRecognizer
        model_name = os.environ.get(
            "EMOTION_MODEL_NAME", "enet_b0_8_best_afew"
        )
        device = "cuda" if _cuda_available() else "cpu"
        logger.info(
            f"Initialising EmotiEffLib recognizer | model='{model_name}' device='{device}'"
        )
        _emotiefflib_recognizer = EmotiEffLibRecognizer(
            engine="torch", model_name=model_name, device=device
        )
    return _emotiefflib_recognizer


def _cuda_available() -> bool:
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False


def _run_emotiefflib(pil_image_for_model):
    """
    Run EmotiEffLib inference on a (cropped) PIL image.

    Returns:
        tuple: (emotion_label: str, confidence: float)
    """
    import numpy as np

    recognizer = _get_emotiefflib_recognizer()
    # EmotiEffLibRecognizer expects a numpy array (RGB)
    face_np = np.array(pil_image_for_model.convert("RGB"))
    labels, scores = recognizer.predict_emotions(face_np, logits=False)
    # For a single image, labels is a one-element list and scores has shape (1, N)
    emotion_label = labels[0] if isinstance(labels, (list, tuple)) else labels
    confidence = float(np.max(scores))
    return emotion_label, round(confidence, 2)


# ---------------------------------------------------------------------------
# Dima / HuggingFace transformers backend
# ---------------------------------------------------------------------------

_video_pipe = None


def _get_dima_pipeline():
    """Lazily initialise and cache the HuggingFace image-classification pipeline."""
    global _video_pipe
    if _video_pipe is None:
        from transformers import pipeline
        model_name = os.environ.get(
            "EMOTION_MODEL_NAME", "dima806/facial_emotions_image_detection"
        )
        logger.info(
            f"Initialising Dima/HuggingFace pipeline | model='{model_name}'"
        )
        _video_pipe = pipeline("image-classification", model=model_name)
    return _video_pipe


def _run_dima(pil_image_for_model):
    """
    Run HuggingFace transformers pipeline inference on a (cropped) PIL image.

    Returns:
        tuple: (emotion_label: str, confidence: float)
    """
    pipe = _get_dima_pipeline()
    predictions = pipe(pil_image_for_model)
    if predictions:
        top = predictions[0]
        return top.get("label"), round(top.get("score", 0.0), 2)
    return None, None


# ---------------------------------------------------------------------------
# Public helpers (kept for backward compatibility / lazy init callers)
# ---------------------------------------------------------------------------

def get_emotion_pipeline():
    """Return the active emotion pipeline/recognizer object (for backward compat)."""
    backend = _get_backend()
    if backend == BACKEND_EMOTIEFFLIB:
        return _get_emotiefflib_recognizer()
    return _get_dima_pipeline()


# ---------------------------------------------------------------------------
# YOLO face detector (shared by both backends)
# ---------------------------------------------------------------------------

_face_detector = None


def get_face_detector():
    global _face_detector
    if _face_detector is None:
        from ultralytics import YOLO
        from huggingface_hub import hf_hub_download
        model_name = os.environ.get(
            "FACE_DETECTOR_MODEL_NAME", "arnabdhar/YOLOv8-Face-Detection"
        )
        logger.info(f"Initializing YOLO face detector with model: {model_name}")
        model_path = hf_hub_download(repo_id=model_name, filename="model.pt")
        _face_detector = YOLO(model_path)
    return _face_detector


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def analyze_emotion(image_path):
    """
    Reads a saved image file (or in-memory frame) and analyses the dominant emotion.

    The emotion model backend is selected via the ``EMOTION_MODEL_BACKEND``
    environment variable:

    * ``"emotiefflib"`` (default) – uses the HSEmotion / EmotiEffLib library.
      Configure the model with ``EMOTION_MODEL_NAME`` (e.g. ``enet_b0_8_best_afew``).
    * ``"dima"`` – uses a HuggingFace ``image-classification`` pipeline.
      Configure the model with ``EMOTION_MODEL_NAME``
      (e.g. ``dima806/facial_emotions_image_detection``).

    Returns:
        tuple: (emotion_recognized, confidence_score,
                face_recognition_milliseconds, emotion_recognition_milliseconds)
               or (None, None, None, None) if failed.
    """
    try:
        from PIL import Image

        if isinstance(image_path, str):
            if not os.path.exists(image_path):
                logger.error(f"File {image_path} does not exist.")
                return None, None, None, None
            pil_image = Image.open(image_path)
        elif isinstance(image_path, np.ndarray):
            # Convert BGR (OpenCV) to RGB
            rgb_frame = cv2.cvtColor(image_path, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(rgb_frame)
        elif isinstance(image_path, Image.Image):
            pil_image = image_path
        else:
            logger.error(f"Unsupported image type: {type(image_path)}")
            return None, None, None, None

        # ------------------------------------------------------------------
        # Face detection with YOLO (shared across backends)
        # ------------------------------------------------------------------
        face_detected = False
        pil_image_for_model = pil_image  # fallback – overwritten when face found
        face_start = time.perf_counter()
        try:
            face_detector = get_face_detector()
            results = face_detector(pil_image, verbose=False)
            if results and len(results[0].boxes) > 0:
                best_box = results[0].boxes[0]
                xyxy = best_box.xyxy[0].tolist()  # [xmin, ymin, xmax, ymax]
                xmin, ymin, xmax, ymax = map(int, xyxy)

                # Clip coordinates to image boundaries
                width, height = pil_image.size
                xmin = max(0, xmin)
                ymin = max(0, ymin)
                xmax = min(width, xmax)
                ymax = min(height, ymax)

                cropped_image = pil_image.crop((xmin, ymin, xmax, ymax))

                # Save the cropped face with _face_cropped added at the end of the filename
                if isinstance(image_path, str):
                    base, ext = os.path.splitext(image_path)
                    cropped_path = f"{base}_face_cropped{ext}"
                    cropped_image.save(cropped_path)
                    logger.info(f"Successfully saved cropped face to {cropped_path}")

                pil_image_for_model = cropped_image
                face_detected = True
                logger.info("Face detected successfully by YOLO face detector.")
            else:
                logger.info("No face detected in the image by YOLO face detector.")
        except Exception as detection_err:
            logger.error(f"Error during face detection/cropping: {detection_err}.")
        face_end = time.perf_counter()
        face_recognition_ms = int(round((face_end - face_start) * 1000))

        if not face_detected:
            logger.info("Skipping emotion analysis because no face was detected.")
            return "none", 0.0, face_recognition_ms, None

        # ------------------------------------------------------------------
        # Emotion recognition – dispatch to selected backend
        # ------------------------------------------------------------------
        backend = _get_backend()
        logger.info(f"Running emotion analysis with backend='{backend}'")

        emotion_start = time.perf_counter()

        if backend == BACKEND_EMOTIEFFLIB:
            emotion_recognized, confidence_score = _run_emotiefflib(pil_image_for_model)
        else:  # BACKEND_DIMA
            emotion_recognized, confidence_score = _run_dima(pil_image_for_model)

        emotion_end = time.perf_counter()
        emotion_recognition_ms = int(round((emotion_end - emotion_start) * 1000))

        if emotion_recognized is not None:
            logger.info(
                f"Detected emotion: '{emotion_recognized}' "
                f"with confidence score: {confidence_score} "
                f"(backend='{backend}')"
            )
            return emotion_recognized, confidence_score, face_recognition_ms, emotion_recognition_ms

        return None, None, face_recognition_ms, emotion_recognition_ms

    except Exception as e:
        logger.error(f"An error occurred during emotion analysis: {e}")
        return None, None, None, None