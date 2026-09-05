import cv2
import librosa
import numpy as np
from transformers import pipeline
from PIL import Image

# 1. Initialize the ready-to-use Hugging Face models
print("Loading models from Hugging Face...")
audio_pipe = pipeline("audio-classification", model="r-f/wav2vec-english-speech-emotion-recognition")
# New fixed line
video_pipe = pipeline("image-classification", model="dima806/facial_emotions_image_detection")


def analyze_video_emotion(video_path):
    # --- STEP 1: Process Audio ---
    print("Extracting and analyzing audio...")
    # Librosa can read the audio directly from most video files (mp4, mkv, etc.)
    try:
        audio_data, sampling_rate = librosa.load(video_path, sr=16000)
        audio_results = audio_pipe(audio_data)
    except Exception as e:
        print(f"Audio processing failed (maybe video has no sound): {e}")
        audio_results = []

    # --- STEP 2: Process Video Frames ---
    print("Extracting and analyzing video frames...")
    cap = cv2.VideoCapture(video_path)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # We will sample 5 frames spaced evenly throughout the video to get a snapshot
    frame_indices = np.linspace(0, frame_count - 1, num=5, dtype=int)
    video_results = []

    for idx in frame_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        success, frame = cap.read()
        if not success:
            continue

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(frame_rgb)
        frame_prediction = video_pipe(pil_image)
        video_results.append(frame_prediction)

    cap.release()

    # --- STEP 3: Print Raw Predictions ---
    print("\n--- RESULTS ---")
    if audio_results:
        print(f"Top Audio Emotion: {audio_results[0]['label']} (Confidence: {audio_results[0]['score']:.2f})")

    if video_results:
        # Looking at the prediction of the very first sampled frame for brevity
        print(f"Initial Video Emotion: {video_results[0][0]['label']} (Confidence: {video_results[0][0]['score']:.2f})")
    if audio_results:
        print("\n--- ALL AUDIO EMOTION SCORES ---")
        # Removed the [:3] slice to print everything the model returned
        for res in audio_results:
            print(f"  {res['label'].ljust(12)}: {res['score']:.4f}")
    if video_results:
        print("\n--- ALL VIDEO EMOTION SCORES (Per Sampled Frame) ---")
        for i, frame_res in enumerate(video_results):
            print(f"\n[Frame {i + 1} Predictions]:")
            # Loop through all emotion scores for this specific frame
            for prediction in frame_res:
                print(f"  {prediction['label'].ljust(12)}: {prediction['score']:.4f}")

# Run it on your file
analyze_video_emotion("//test_video/happy_man2.mp4")