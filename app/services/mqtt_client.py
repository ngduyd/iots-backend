import asyncio
import queue as pyqueue
import paho.mqtt.client as mqtt
from datetime import datetime, timezone
from app.core import config
from app.services.database import update_sensor_status


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected successfully")
        client.subscribe(config.MQTT_TOPIC)
    else:
        print(f"Connection failed with code {rc}")


def on_message(client, userdata, msg):
    loop = userdata.get("loop") if userdata else None
    message_queue = userdata.get("queue") if userdata else None
    received_at = datetime.now(timezone.utc)

    sensor_id = msg.topic.split("/sensors/")[1] if "/sensors/" in msg.topic else None
    payload = msg.payload.decode()

    if payload.strip().lower() == "offline":
        if sensor_id and loop:
            asyncio.run_coroutine_threadsafe(update_sensor_status(sensor_id, "offline"), loop)
        return

    if loop and message_queue:
        def _enqueue():
            try:
                message_queue.put_nowait((sensor_id, payload, received_at))
            except pyqueue.Full:
                pass

        loop.call_soon_threadsafe(_enqueue)


def create_mqtt_client(loop=None, queue=None):
    client = mqtt.Client()
    if config.MQTT_USERNAME and config.MQTT_PASSWORD:
        client.username_pw_set(config.MQTT_USERNAME, config.MQTT_PASSWORD)
    client.on_connect = on_connect
    client.on_message = on_message
    client.user_data_set({"loop": loop, "queue": queue})
    return client
