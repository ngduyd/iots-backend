import os
from dotenv import load_dotenv

load_dotenv()

MQTT_BROKER = os.environ.get("MQTT_BROKER")
MQTT_PORT = int(os.environ.get("MQTT_PORT", 1883))
MQTT_USERNAME = os.environ.get("MQTT_USERNAME")
MQTT_PASSWORD = os.environ.get("MQTT_PASSWORD")
MQTT_TOPIC = os.environ.get("MQTT_TOPIC", "#")

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = int(os.environ.get("DB_PORT", 5432))
DB_NAME = os.environ.get("DB_NAME", "sensors_db")
DB_USER = os.environ.get("DB_USER", "user")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "password")
DB_READ_LOCK_TIMEOUT_MS = int(os.environ.get("DB_READ_LOCK_TIMEOUT_MS", 200))
DB_READ_STATEMENT_TIMEOUT_MS = int(os.environ.get("DB_READ_STATEMENT_TIMEOUT_MS", 3000))

HTTP_HOST = os.environ.get("HTTP_HOST", "0.0.0.0")
HTTP_PORT = int(os.environ.get("HTTP_PORT", 8000))

AUTH_USERNAME = os.environ.get("AUTH_USERNAME", "admin")
AUTH_PASSWORD = os.environ.get("AUTH_PASSWORD", "admin123")
SESSION_SECRET = os.environ.get("SESSION_SECRET", "change-me-in-production")
SESSION_MAX_AGE_SECONDS = int(os.environ.get("SESSION_MAX_AGE_SECONDS", 3600))
CAMERA_ACCESS_TOKEN_TTL_SECONDS = int(os.environ.get("CAMERA_ACCESS_TOKEN_TTL_SECONDS", 60))
STREAM_BASE_URL = os.environ.get("STREAM_BASE_URL", "localhost:8080/live")

SENSOR_OFFLINE_TIMEOUT = int(os.environ.get("SENSOR_OFFLINE_TIMEOUT", 120))
OFFLINE_MONITOR_INTERVAL_SECONDS = int(os.environ.get("OFFLINE_MONITOR_INTERVAL_SECONDS", 5))

MQTT_QUEUE_MAXSIZE = int(os.environ.get("MQTT_QUEUE_MAXSIZE", 5000))
DB_WORKER_BATCH_SIZE = int(os.environ.get("DB_WORKER_BATCH_SIZE", 200))
DB_WORKER_FLUSH_INTERVAL_MS = int(os.environ.get("DB_WORKER_FLUSH_INTERVAL_MS", 250))

CAMERA_CAPTURE_INTERVAL_SECONDS = int(os.environ.get("CAMERA_CAPTURE_INTERVAL_SECONDS", 5))
CAMERA_MAX_INFLIGHT = int(os.environ.get("CAMERA_MAX_INFLIGHT", 20))
CAMERA_CAPTURE_TASK_TIMEOUT_SECONDS = int(os.environ.get("CAMERA_CAPTURE_TASK_TIMEOUT_SECONDS", 4))
CAMERA_CAPTURE_JITTER_SECONDS = int(os.environ.get("CAMERA_CAPTURE_JITTER_SECONDS", 5))
CAMERA_LIST_REFRESH_SECONDS = int(os.environ.get("CAMERA_LIST_REFRESH_SECONDS", 300))

AI_API_URL = os.environ.get("AI_API_URL", "http://100.123.114.97:9000/api/v1")
