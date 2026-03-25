from datetime import datetime, timezone

import paho.mqtt.client as mqtt

from app.core import config
from app.services import manager


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected successfully")
        client.subscribe(config.MQTT_TOPIC)
    else:
        print(f"Connection failed with code {rc}")


def on_message(client, userdata, msg):
    loop = userdata.get("loop") if userdata else None
    queue = userdata.get("queue") if userdata else None
    received_at = datetime.now(timezone.utc)

    sensor_id = msg.topic.split("/sensors/")[1] if "/sensors/" in msg.topic else None
    payload = msg.payload.decode()

    manager.record_sensor_activity(sensor_id, loop)

    if loop and queue:
        loop.call_soon_threadsafe(queue.put_nowait, (sensor_id, payload, received_at))


def create_mqtt_client(loop=None, queue=None):
    client = mqtt.Client()
    if config.MQTT_USERNAME and config.MQTT_PASSWORD:
        client.username_pw_set(config.MQTT_USERNAME, config.MQTT_PASSWORD)
    client.on_connect = on_connect
    client.on_message = on_message
    client.user_data_set({"loop": loop, "queue": queue})
    return client
