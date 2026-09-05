# import cv2
# import os
# import time
#
# # 1. CHANGED: Use the main entity instead of the live_view proxy
# HA_URL = "http://192.168.1.216:8123"
# CAMERA_ENTITY = "camera.tadzio_prawa_gorna"
# TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJlNzMwYjdkNjM2MWQ0ZDNmYjlmMjJlOTdjYjg1NmNlMiIsImlhdCI6MTc4MDIxNjk3MywiZXhwIjoyMDk1NTc2OTczfQ.VrBuYtdiClD93ySjZ4N_3-ekvytDxwXFjwvda-rcgcQ"
#
# SAVE_DIR = "./saved_images"
# os.makedirs(SAVE_DIR, exist_ok=True)
#
#
# def get_camera_details():
#     """Fetches camera attributes and the internal access token."""
#     headers = {"Authorization": f"Bearer {TOKEN}"}
#     try:
#         response = requests.get(f"{HA_URL}/api/states/{CAMERA_ENTITY}", headers=headers)
#         response.raise_for_status()
#         data = response.json()
#
#         attributes = data.get("attributes", {})
#         access_token = attributes.get("access_token")
#
#         # Debug info: see what resolution HA thinks this camera is
#         width = attributes.get("entity_picture_width")
#         height = attributes.get("entity_picture_height")
#         print(f"--- Camera Info: {CAMERA_ENTITY} ---")
#         print(f"Reported Resolution: {width}x{height}")
#         print(f"Available attributes: {list(attributes.keys())}")
#
#         if not access_token:
#             return None
#
#         # We use camera_proxy_stream for the continuous feed
#         return f"{HA_URL}/api/camera_proxy_stream/{CAMERA_ENTITY}?token={access_token}"
#     except Exception as e:
#         print(f"Error fetching camera state: {e}")
#         return None
#
#
# stream_url = get_camera_details()
# if not stream_url:
#     print("Could not find camera. Trying the live_view entity as fallback...")
#     CAMERA_ENTITY = "camera.tadzio_prawa_gorna_live_view"
#     stream_url = get_camera_details()
#
# if not stream_url:
#     exit(1)
#
# cap = cv2.VideoCapture(stream_url)
# # Some streams need a moment to initialize or specific backends
# # cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)
#
# last_saved_time = 0
# save_interval = 2
#
# print(f"Connected to: {stream_url}")
#
# try:
#     while True:
#         ret, frame = cap.read()
#         if not ret:
#             print("Failed to grab frame. Reconnecting...")
#             stream_url = get_camera_details()
#             cap.release()
#             cap = cv2.VideoCapture(stream_url)
#             time.sleep(2)
#             continue
#
#         current_time = time.time()
#         if current_time - last_saved_time >= save_interval:
#             timestamp = time.strftime("%Y%m%d-%H%M%S")
#             filename = f"{SAVE_DIR}/frame_{timestamp}.jpg"
#
#             # Save with high quality
#             cv2.imwrite(filename, frame, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
#
#             # Print the actual resolution of the captured frame
#             h, w, _ = frame.shape
#             print(f"Saved: {filename} (Actual Resolution: {w}x{h})")
#             last_saved_time = current_time
#
#         time.sleep(0.01)
# except KeyboardInterrupt:
#     print("Stopped.")
# finally:
#     cap.release()