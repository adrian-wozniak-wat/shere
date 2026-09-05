import os
import cv2
import requests
import numpy as np


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
            print("Error: Could not decode the image from Home Assistant.")
            return None

        # Save the image to the specified directory
        cv2.imwrite(filename, frame, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
        print(f"Successfully saved snapshot to {filename}")
        return filename

    except Exception as e:
        print(f"An error occurred while saving snapshot: {e}")
        return None


_video_pipe = None
_face_detector = None


def get_emotion_pipeline():
    global _video_pipe
    if _video_pipe is None:
        from transformers import pipeline
        model_name = os.environ.get('EMOTION_MODEL_NAME', 'dima806/facial_emotions_image_detection')
        print(f"Initializing emotion pipeline with model: {model_name}")
        _video_pipe = pipeline("image-classification", model=model_name)
    return _video_pipe


def get_face_detector():
    global _face_detector
    if _face_detector is None:
        from ultralytics import YOLO
        from huggingface_hub import hf_hub_download
        model_name = os.environ.get('FACE_DETECTOR_MODEL_NAME', 'arnabdhar/YOLOv8-Face-Detection')
        print(f"Initializing YOLO face detector with model: {model_name}")
        model_path = hf_hub_download(repo_id=model_name, filename="model.pt")
        _face_detector = YOLO(model_path)
    return _face_detector


import time


def analyze_emotion(image_path):
    """
    Reads a saved image file and analyzes the dominant emotion.

    Returns:
        tuple: (emotion_recognized, confidence_score, face_recognition_milliseconds, emotion_recognition_milliseconds)
               or (None, None, None, None) if failed.
    """
    try:
        from PIL import Image

        if isinstance(image_path, str):
            if not os.path.exists(image_path):
                print(f"Error: File {image_path} does not exist.")
                return None, None, None, None
            pil_image = Image.open(image_path)
        elif isinstance(image_path, np.ndarray):
            # Convert BGR (OpenCV) to RGB
            rgb_frame = cv2.cvtColor(image_path, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(rgb_frame)
        elif isinstance(image_path, Image.Image):
            pil_image = image_path
        else:
            print(f"Error: Unsupported image type: {type(image_path)}")
            return None, None, None, None

        # Detect face with YOLO and crop it
        face_detected = False
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
                    print(f"Successfully saved cropped face to {cropped_path}")

                pil_image_for_model = cropped_image
                face_detected = True
            else:
                print("Warning: No face detected by YOLO.")
        except Exception as detection_err:
            print(f"Error during face detection/cropping: {detection_err}.")
        face_end = time.perf_counter()
        face_recognition_ms = int(round((face_end - face_start) * 1000))

        if not face_detected:
            return "none", 0.0, face_recognition_ms, None

        emotion_start = time.perf_counter()
        pipe = get_emotion_pipeline()
        predictions = pipe(pil_image_for_model)
        emotion_end = time.perf_counter()
        emotion_recognition_ms = int(round((emotion_end - emotion_start) * 1000))

        if predictions:
            # The predictions are sorted by score descending, so the first one is dominant
            top_prediction = predictions[0]
            emotion_recognized = top_prediction.get("label")
            confidence_score = round(top_prediction.get("score", 0.0), 2)
            return emotion_recognized, confidence_score, face_recognition_ms, emotion_recognition_ms

        return None, None, face_recognition_ms, emotion_recognition_ms

    except Exception as e:
        print(f"An error occurred during emotion analysis: {e}")
        return None, None, None, None