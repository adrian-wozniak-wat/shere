import cv2
import os
import time
import requests
import json

# Configuration
HA_URL = "http://192.168.1.216:8123"
CAMERA_ENTITY = "camera.tadzio_prawa_gorna_live_view" 
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJlNzMwYjdkNjM2MWQ0ZDNmYjlmMjJlOTdjYjg1NmNlMiIsImlhdCI6MTc4MDIxNjk3MywiZXhwIjoyMDk1NTc2OTczfQ.VrBuYtdiClD93ySjZ4N_3-ekvytDxwXFjwvda-rcgcQ"

SAVE_DIR = "saved_images"
os.makedirs(SAVE_DIR, exist_ok=True)

def get_high_res_stream_url():
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
    }
    
    try:
        # 1. Get FULL attributes to find the high-res stream source
        response = requests.get(f"{HA_URL}/api/states/{CAMERA_ENTITY}", headers=headers)
        response.raise_for_status()
        state_data = response.json()
        attrs = state_data.get("attributes", {})
        
        print("\n--- Full Debug Attributes ---")
        # Print all attributes so we can find hidden stream URLs
        for k, v in attrs.items():
            if k != "access_token":
                print(f"{k}: {v}")
        
        # 2. Check for common high-res attributes
        # Many cameras (like Reolink, Wyze, Amcrest) provide the RTSP URL here
        if "stream_source" in attrs:
            print(f"\n[!] FOUND DIRECT SOURCE: {attrs['stream_source']}")
            return attrs["stream_source"]
            
        # 3. If no direct source, and MJPEG is low-res, the high-res stream is usually HLS
        # We can try to get the HLS stream from the master stream endpoint
        access_token = attrs.get("access_token")
        
        # This is the MJPEG proxy (which you said is low quality)
        mjpeg_url = f"{HA_URL}/api/camera_proxy_stream/{CAMERA_ENTITY}?token={access_token}"
        
        # Let's try to find an HLS stream if the stream component is active
        # The 'Live View' in the browser uses a different websocket-negotiated stream.
        # But we can try to guess the HLS path:
        hls_url = f"{HA_URL}/api/cameras/stream/{CAMERA_ENTITY}"
        # (This usually requires a session, but let's see)
        
        return mjpeg_url 
            
    except Exception as e:
        print(f"Error: {e}")
        return None

stream_url = get_high_res_stream_url()

if not stream_url:
    exit(1)

print(f"\nConnecting to: {stream_url}")
cap = cv2.VideoCapture(stream_url)

# Try to force resolution in case the MJPEG stream supports it
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

last_saved_time = 0
save_interval = 2 

try:
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Failed to grab frame. Retrying...")
            time.sleep(2)
            continue

        h, w, _ = frame.shape
        current_time = time.time()

        if current_time - last_saved_time >= save_interval:
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            filename = f"{SAVE_DIR}/frame_{timestamp}.jpg"
            
            cv2.imwrite(filename, frame, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
            print(f"Captured: {filename} Resolution: {w}x{h}")
            last_saved_time = current_time

        time.sleep(0.01)

except KeyboardInterrupt:
    print("Stopped.")
finally:
    cap.release()
