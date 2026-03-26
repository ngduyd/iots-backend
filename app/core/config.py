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

HTTP_HOST = os.environ.get("HTTP_HOST", "0.0.0.0")
HTTP_PORT = int(os.environ.get("HTTP_PORT", 8000))

AUTH_USERNAME = os.environ.get("AUTH_USERNAME", "admin")
AUTH_PASSWORD = os.environ.get("AUTH_PASSWORD", "admin123")
SESSION_SECRET = os.environ.get("SESSION_SECRET", "change-me-in-production")
SESSION_MAX_AGE_SECONDS = int(os.environ.get("SESSION_MAX_AGE_SECONDS", 3600))
CAMERA_ACCESS_TOKEN_TTL_SECONDS = int(os.environ.get("CAMERA_ACCESS_TOKEN_TTL_SECONDS", 60))
STREAM_BASE_URL = os.environ.get("STREAM_BASE_URL", "localhost:8080/live")

SENSOR_OFFLINE_TIMEOUT = int(os.environ.get("SENSOR_OFFLINE_TIMEOUT", 120))