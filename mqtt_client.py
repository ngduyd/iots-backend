import paho.mqtt.client as mqtt
import config
from db import save_message, update_sensor_status
import manager
import asyncio

def on_connect(client, userdata, flags, rc):
    """Callback for MQTT connection."""
    if rc == 0:
        print("Connected successfully")
        client.subscribe(config.MQTT_TOPIC)
    else:
        print(f"Connection failed with code {rc}")

def on_message(client, userdata, msg):
    """Callback for MQTT messages with async support."""
    loop = userdata.get('loop') if userdata else None
    
    if msg.topic.endswith("/cmd"):
        sensor_name = msg.topic.rsplit('/', 1)[0]
        status = msg.payload.decode().lower()
        if loop:
            asyncio.run_coroutine_threadsafe(update_sensor_status(sensor_name, status), loop)
        manager.sensor_status[sensor_name] = status
    else:
        sensor_name = msg.topic.rsplit('/', 1)[0]
        payload = msg.payload.decode()
        manager.record_sensor_activity(sensor_name, loop)
        if loop:
            asyncio.run_coroutine_threadsafe(save_message(sensor_name, payload), loop)

def create_mqtt_client(loop=None):
    """Creates and configures an MQTT client."""
    client = mqtt.Client()
    if config.MQTT_USERNAME and config.MQTT_PASSWORD:
        client.username_pw_set(config.MQTT_USERNAME, config.MQTT_PASSWORD)
    client.on_connect = on_connect
    client.on_message = on_message
    client.user_data_set({'loop': loop})
    return client