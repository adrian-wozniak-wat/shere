#!/usr/bin/env python3
import os
import csv
import json
import random
import mimetypes
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

PORT = int(os.environ.get("MOCK_HA_PORT", 8123))
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PHOTOS_DIR = os.path.join(SCRIPT_DIR, "mock_photos")
CSV_PATH = os.path.join(SCRIPT_DIR, "sensor_data.csv")

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""
    daemon_threads = True


class SensorDataReader:
    def __init__(self, csv_path):
        self.csv_path = csv_path
        self.entity_rows = {}
        self.load_data()

    def load_data(self):
        if not os.path.exists(self.csv_path):
            print(f"[MockHA] CSV file not found at {self.csv_path}.")
            return

        self.entity_rows = {}
        try:
            with open(self.csv_path, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    eid = row.get("entity_id", "").strip()
                    if eid:
                        if eid not in self.entity_rows:
                            self.entity_rows[eid] = []
                        self.entity_rows[eid].append(row)

            print(f"[MockHA] Loaded sensor mock data for entities: {list(self.entity_rows.keys())}")
        except Exception as e:
            print(f"[MockHA] Error reading CSV sensor data: {e}")

    def get_state_and_attributes(self, entity_id):
        if not self.entity_rows:
            self.load_data()

        # Check exact match or fallback
        target_eid = entity_id
        if target_eid not in self.entity_rows:
            if entity_id in ("mock_camera", "camera.mock_camera"):
                return "idle", {"friendly_name": "Mock Camera"}
            elif self.entity_rows:
                target_eid = next(iter(self.entity_rows))

        if target_eid not in self.entity_rows:
            return "21.5", {"unit_of_measurement": "°C", "friendly_name": entity_id}

        rows = self.entity_rows[target_eid]
        row = random.choice(rows)

        state = row.get("state", "unknown")
        attributes = {}
        if row.get("unit_of_measurement"):
            attributes["unit_of_measurement"] = row.get("unit_of_measurement")
        if row.get("friendly_name"):
            attributes["friendly_name"] = row.get("friendly_name")

        for k, v in row.items():
            if k not in ("entity_id", "state", "unit_of_measurement", "friendly_name") and v:
                attributes[k] = v

        return state, attributes

    def get_all_states(self):
        states = []
        for eid in self.entity_rows:
            st, attrs = self.get_state_and_attributes(eid)
            states.append({
                "entity_id": eid,
                "state": st,
                "attributes": attrs
            })
        states.append({
            "entity_id": "mock_camera",
            "state": "idle",
            "attributes": {"friendly_name": "Mock Camera"}
        })
        return states


sensor_reader = SensorDataReader(CSV_PATH)


class MockHAHandler(BaseHTTPRequestHandler):

    @classmethod
    def get_random_photo(cls):
        files = []
        if os.path.exists(PHOTOS_DIR):
            for entry in os.listdir(PHOTOS_DIR):
                ext = os.path.splitext(entry)[1].lower()
                if ext in IMAGE_EXTENSIONS:
                    files.append(os.path.join(PHOTOS_DIR, entry))

        if not files:
            print(f"[MockHA] Warning: No supported image files found in {PHOTOS_DIR}")
            return None, "image/jpeg"

        photo_path = random.choice(files)

        content_type, _ = mimetypes.guess_type(photo_path)
        if not content_type:
            content_type = "image/jpeg"

        return photo_path, content_type

    def do_GET(self):
        path = self.path.rstrip('/')

        # 1. API Status check
        if path == "/api" or path == "":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"message": "API running."}).encode("utf-8"))
            return

        # 2. Camera proxy endpoint: /api/camera_proxy/<camera_id>
        if "/api/camera_proxy/" in self.path:
            photo_path, content_type = self.get_random_photo()
            if photo_path and os.path.exists(photo_path):
                with open(photo_path, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                print(f"[MockHA] Served camera proxy snapshot using random photo '{os.path.basename(photo_path)}'")
            else:
                self.send_response(404)
                self.end_headers()
            return

        # 3. Entity state endpoint: /api/states/<entity_id> or /api/states
        if "/api/states/" in self.path:
            entity_id = self.path.split("/api/states/")[-1].strip('/')
            state, attributes = sensor_reader.get_state_and_attributes(entity_id)
            response_data = {
                "entity_id": entity_id,
                "state": state,
                "attributes": attributes
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response_data).encode("utf-8"))
            return

        if path == "/api/states":
            states = sensor_reader.get_all_states()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(states).encode("utf-8"))
            return

        # 4. Mock every other HA endpoint
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"message": "API running.", "state": "ok"}).encode("utf-8"))

    def do_HEAD(self):
        if "/api/camera_proxy/" in self.path:
            photo_path, content_type = self.get_random_photo()
            if photo_path and os.path.exists(photo_path):
                size = os.path.getsize(photo_path)
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(size))
                self.end_headers()
            else:
                self.send_response(404)
                self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

    def log_message(self, format, *args):
        # Suppress verbose server log output
        pass


def run():
    server_address = ('', PORT)
    httpd = ThreadedHTTPServer(server_address, MockHAHandler)
    print(f"[MockHA] Mock Home Assistant server running on http://127.0.0.1:{PORT}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    run()
