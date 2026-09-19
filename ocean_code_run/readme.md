# Ocean Code Run - Standalone Presentation & Demo Environment

> **DISCLAIMER:**  
> The code, scripts, and mock services in this directory (`ocean_code_run/`) are designed **purely for presentation, demonstration, and offline evaluation purposes**.  
> This setup allows the application to run completely standalone without requiring external infrastructure such as PostgreSQL, RabbitMQ, Celery workers, or an active Home Assistant instance.

---

## 🎯 Purpose

This environment allows you to showcase the full functionality of the **HA Emotion Research** platform (including live dashboard views, camera face detection, emotion analysis, and Home Assistant entity polling) in an offline presentation setup with **zero external network dependencies**.

---

## 📁 Directory Structure & Components

| File / Folder | Description |
| :--- | :--- |
| **`run.sh`** | Main entrypoint script. Sets up SQLite DB, initializes models & entities, launches background mock services, and starts the Django web server on `0.0.0.0:8000`. |
| **`init_db.py`** | Initializes the SQLite database (`db.sqlite3`), runs migrations, creates the superuser (`admin`), and seeds mock entities from `sensor_data.csv`. |
| **`mock_ha_server.py`** | Lightweight HTTP server running on `127.0.0.1:8123` that mocks Home Assistant REST API endpoints (`/api/`, `/api/camera_proxy/`, `/api/states/`). |
| **`poll_runner.py`** | Standalone polling loop process that executes emotion analysis cycles every 5 seconds without requiring Celery or RabbitMQ. |
| **`sensor_data.csv`** | Contains sample sensor metric data (temperature, humidity, power, motion, light status, CO2) used by the mock server across polling cycles. |
| **`ocean_photos/`** | Directory containing sample JPEG/PNG images served sequentially by `mock_ha_server.py` to simulate camera feeds. |
| **`models_cache/`** | Bundled Hugging Face & YOLO machine learning model files for 100% offline face detection and emotion recognition. |
| **`bundle_models.py`** | Helper script to package ML models locally into `models_cache/`. |

---

## 🚀 How to Run the Presentation Environment

1. **Navigate to the project root directory**:
   ```bash
   cd /path/to/ha_emotion_research
   ```

2. **Execute the offline launcher script**:
   ```bash
   ./ocean_code_run/run.sh
   ```

3. **Access the Web Dashboard**:
   - Open your browser and navigate to `http://localhost:8000`.
   - Default login credentials:
     - **Username**: `admin`
     - **Password**: `admin123`

4. **Stopping the Presentation**:
   - Press `Ctrl + C` in the terminal. The script will automatically shut down the background mock Home Assistant server, poll runner, and Django web server.
