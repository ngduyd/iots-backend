import os
from dotenv import load_dotenv

# load_dotenv()

# MQTT Broker configuration
MQTT_BROKER = os.environ.get("MQTT_BROKER")
MQTT_PORT = int(os.environ.get("MQTT_PORT", 1883))
MQTT_USERNAME = os.environ.get("MQTT_USERNAME")
MQTT_PASSWORD = os.environ.get("MQTT_PASSWORD")
MQTT_TOPIC = os.environ.get("MQTT_TOPIC", "#")

# Database configuration
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = int(os.environ.get("DB_PORT", 5432))
DB_NAME = os.environ.get("DB_NAME", "sensors_db")
DB_USER = os.environ.get("DB_USER", "user")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "password")

# Network Service configuration
NETWORK_SERVICE_HOST = os.environ.get("NETWORK_SERVICE_HOST", "localhost")
NETWORK_SERVICE_PORT = int(os.environ.get("NETWORK_SERVICE_PORT", 50051))

# Reciver configuration
RECIVER_HOST = os.environ.get("RECIVER_HOST", "localhost")
RECIVER_PORT = int(os.environ.get("RECIVER_PORT", 50051))

# Other configurations
DEVICE_API_KEY = os.environ.get("device_api_key", "default_api_key")