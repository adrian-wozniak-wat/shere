# SHERE User Manual

## 💻 System Requirements

Before deploying SHERE, ensure your host environment meets the following minimum requirements:

*   **Software**: [Docker](https://www.docker.com/) with [Docker Compose](https://docs.docker.com/compose/)
*   **Architecture**: x86_64 / x64 CPU
*   **Processor**: Dual-core CPU (2 Cores minimum)
*   **Memory**: 4 GB RAM minimum
*   **Network & Connectivity**: Accessible Home Assistant instance with exposed REST API (and a valid Long-Lived Access Token)
*   **Optional GPU Acceleration**: An NVIDIA graphics card (e.g. RTX series) can be passed through to accelerate deep learning model inference. To enable GPU support:
    1. Install proper NVIDIA host drivers.
    2. Install `nvidia-container-toolkit` on the host machine.
    3. Uncomment the NVIDIA GPU `deploy` block in `docker-compose.yml` under the `celery_worker` service.

---

## 🚀 Quick Start & Installation

Ensure you have [Docker](https://www.docker.com/) and [Docker Compose](https://docs.docker.com/compose/) installed.

### 1. Start Services
SHERE uses a pre-built Docker image hosted on GitHub Container Registry (`ghcr.io/adrian-wozniak-wat/shere:latest`). Simply run:

```bash
docker compose up -d
```

This will automatically pull the image and run five background services:
*   `db`: PostgreSQL database server.
*   `rabbitmq`: The message broker queue.
*   `web`: The Django web portal (accessible at `http://localhost:8000`).
*   `celery_worker`: Background process handler carrying out API requests and deep learning tasks.
*   `celery_beat`: Cron scheduler dispatching tasks every 30 seconds.

> [!IMPORTANT]
> **Security Notice**: Creating a `.env` file is optional because fallback default values are built-in for zero-configuration startup. However, **for security reasons, it is strongly recommended to set custom environment variables locally** in production or non-isolated deployments.

#### Environment Variables

The following environment variables can be customized:

| Variable | Description | Default |
| :--- | :--- | :--- |
| `DB_USER` | PostgreSQL database user | `admin` |
| `DB_PASSWORD` | PostgreSQL database password | `admin123` |
| `DB_HOST` | Database host address | `127.0.0.1` |
| `RABBIT_USER` | RabbitMQ broker username | `guest` |
| `RABBIT_PASSWORD` | RabbitMQ broker password | `guest` |
| `ENCRYPTION_KEY` | Symmetric Fernet key for encrypting stored access tokens | Built-in default key |
| `APP_USER` | Initial Django admin username created on startup | `admin` |
| `APP_PASS` | Initial Django admin password created on startup | `admin123` |
| `EMOTION_MODEL_NAME` | Deep learning emotion classification model | `dima806/facial_emotions_image_detection` |
| `CELERY_WORKER_CONCURRENCY` | Celery worker process concurrency | `2` |
| `DOCKER_IMAGE` | SHERE container image registry path | `ghcr.io/adrian-wozniak-wat/shere:latest` |

#### Example `.env` File:

```env
# Database & Broker Credentials
DB_USER=custom_db_user
DB_PASSWORD=custom_db_password
RABBIT_USER=custom_rabbit_user
RABBIT_PASSWORD=custom_rabbit_password

# Secret Fernet Encryption Key
# Generate using: python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY=your-custom-generated-fernet-key

# Application Superuser Credentials
APP_USER=custom_admin
APP_PASS=custom_admin_password

# Optional Performance & Image Settings
CELERY_WORKER_CONCURRENCY=2
DOCKER_IMAGE=ghcr.io/adrian-wozniak-wat/shere:latest
```

### 2. Create a Superuser (Optional/Manual)
The `web` container automatically creates a superuser on startup using `APP_USER` and `APP_PASS` (defaulting to `admin` / `admin123`). If you wish to manually create additional admin accounts, run:

```bash
docker compose exec web python src/manage.py createsuperuser
```

### 3. Verify the App Status
Access `http://localhost:8000` in your web browser, log in using your superuser credentials, navigate to the **Run** tab, and execute the connection diagnostic suite to verify API credentials, sensor bindings, and model availability.

---

## 🖥️ GUI Management

By default, the SHERE web interface is accessible at the IP address of the host machine on port **8000** (e.g., `http://<HOST_IP>:8000` or `http://localhost:8000`).

The web dashboard allows users to manage Home Assistant connection credentials, configure tracked entities and cameras, perform diagnostic dry-runs, control polling jobs, and view or export collected research logs.

### 1. Configuration Setup

Before SHERE can capture data, you must configure the connection to your Home Assistant instance, register the sensors (entities) you wish to monitor, and set up the cameras for facial emotion detection.

#### A. Home Assistant Credentials
To allow SHERE to retrieve data from Home Assistant, enter your instance coordinates and authentication token in the **Configuration** page.

![HA Credentials Configuration](docs/images/Configuration%20Page%20Screenshot%20HA%20-%20credentials.png)

* **Host / Port**: The IP address or hostname and port of your Home Assistant server (e.g., `192.168.1.100:8123`).
* **Long-Lived Access Token (LLAT)**:
  * To generate a token in Home Assistant:
    1. Log into your Home Assistant web interface.
    2. Click on your **User Profile / Avatar** (bottom left corner).
    3. Navigate to the **Security** tab.
    4. Scroll down to the **Long-Lived Access Tokens** section at the bottom.
    5. Click **Create Token**, enter a descriptive name (e.g., `SHERE`), and copy the generated token into the SHERE credential configuration form.

> [!NOTE]
> All tokens are encrypted using symmetric Fernet encryption before being persisted in the PostgreSQL database.

#### B. Entities Configuration
Register the smart home sensors from which ambient environment data (e.g., temperature, humidity, lighting, switch states) will be collected during each polling cycle.

![Entities Configuration](docs/images/Configuration%20page%20screenshot%20-%20entities.png)

* **Entity ID**: The exact Home Assistant identifier defined in your HA instance. A single physical device in Home Assistant often provides multiple entities representing different measured metrics.
* **Format**: Sensor entity IDs typically begin with `sensor.` (for example: `sensor.wifi_smart_switch_air_quality` or `sensor.living_room_temperature`).
* **Metadata**: Assign a display name, physical location/room, and unit of measurement for organized data presentation.

#### C. Cameras Configuration
Register the cameras used to capture user facial snapshots for deep-learning emotion analysis.

![Cameras Configuration](docs/images/Configuration%20page%20screenshot%20-%20cameras.png)

* **Camera Entity ID**: Select the entity representing the active camera video stream. Physical camera devices in Home Assistant frequently expose multiple auxiliary entities (such as motion detection sensors, audio sensors, or baby cry alerts). **It is paramount to select the entity that provides the camera video stream**.
* **Format**: Stream entity IDs always begin with `camera.` (for example: `camera.g5_turret_ultra_high_resolution_channel_4`).

---

### 2. Diagnostics & Polling Control

Once credentials, entities, and cameras are configured, navigate to the **Run** tab to perform a diagnostic dry-run and manage data collection.

#### A. Connection & Diagnostic Dry-Run
Before starting automatic background data collection, execute a dry-run diagnostic test to verify API connectivity, token permissions, entity accessibility, and deep learning model readiness.

* **Diagnostic Failure Example**: If credentials or entity IDs are incorrect or unreachable, the diagnostic suite highlights the failing checks:

  ![Diagnostic Test Failure](docs/images/Diagnostic%20test%20screenshot%20-%20failure.png)

* **Diagnostic Success Example**: When all parameters pass verification, green indicators confirm full system readiness:

  ![Diagnostic Test Success](docs/images/Diagnostic%20test%20screenshot%20-%20success.png)

#### B. Polling Interval & Service Control
Once the diagnostic dry-run passes:
* Set your desired **Polling Interval** (e.g., every 30 seconds).
* Click **Start Polling** to initiate periodic background Celery Beat tasks that sample camera snapshots and entity states in parallel.

---

### 3. Viewing & Exporting Results

After polling runs, navigate to the **Results** page to inspect empirical logs and download compiled datasets.

![Result Page Overview](docs/images/Result%20page%20screenshot.png)

* **Unified Data Matrix**: View structured historical poll cycles showing timestamped facial emotion detections (dominant emotion classification and confidence scores) side-by-side with concurrent Home Assistant entity state logs.
* **CSV Data Export**: Download the complete dataset to a `.csv` file with a single click to perform statistical modeling, correlation analysis, or train custom predictive models.
