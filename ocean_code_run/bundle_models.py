#!/usr/bin/env python3
import os
import shutil

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_CACHE_DIR = os.path.join(SCRIPT_DIR, "models_cache", "hub")
USER_HF_HUB = os.path.expanduser("~/.cache/huggingface/hub")

REQUIRED_MODELS = [
    "models--arnabdhar--YOLOv8-Face-Detection",
    "models--dima806--facial_emotions_image_detection"
]


def bundle_models():
    print(f"[BundleModels] Target models directory: {MODELS_CACHE_DIR}")
    os.makedirs(MODELS_CACHE_DIR, exist_ok=True)

    for model_name in REQUIRED_MODELS:
        dst = os.path.join(MODELS_CACHE_DIR, model_name)
        if os.path.exists(dst):
            print(f"[BundleModels] Model '{model_name}' is already present in models_cache.")
            continue

        src = os.path.join(USER_HF_HUB, model_name)
        if os.path.exists(src):
            print(f"[BundleModels] Copying '{model_name}' from HuggingFace cache...")
            shutil.copytree(src, dst)
            print(f"[BundleModels] Copied '{model_name}'.")
        else:
            print(f"[BundleModels] Warning: '{model_name}' not found in '{USER_HF_HUB}'. Attempting download...")
            os.environ["HF_HOME"] = os.path.join(SCRIPT_DIR, "models_cache")
            try:
                from huggingface_hub import hf_hub_download
                from transformers import pipeline
                if "YOLOv8" in model_name:
                    hf_hub_download(repo_id="arnabdhar/YOLOv8-Face-Detection", filename="model.pt")
                if "facial_emotions" in model_name:
                    pipeline("image-classification", model="dima806/facial_emotions_image_detection")
                print(f"[BundleModels] Downloaded '{model_name}' into models_cache.")
            except Exception as e:
                print(f"[BundleModels] Failed to download '{model_name}': {e}")

    print("[BundleModels] Model bundling complete.")


if __name__ == "__main__":
    bundle_models()
