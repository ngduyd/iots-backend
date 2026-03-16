import asyncio
import time

from app.services.database import get_all_sensor_status, update_sensor_status

sensor_status = {}
sensor_last_seen = {}


async def init():
    global sensor_status, sensor_last_seen

    try:
        sensor_status = await get_all_sensor_status()
        now = time.time()
        for sensor, status in sensor_status.items():
            if status == "online":
                sensor_last_seen[sensor] = now
    except Exception as e:
        print(f"Error in init: {e}")


def record_sensor_activity(sensor_id, loop=None):
    global sensor_status, sensor_last_seen

    sensor_last_seen[sensor_id] = time.time()
    current_db_status = sensor_status.get(sensor_id)

    if current_db_status != "online":
        if loop:
            asyncio.run_coroutine_threadsafe(update_sensor_status(sensor_id, "online"), loop)
        sensor_status[sensor_id] = "online"


def check_offline_sensors(timeout_seconds=120, loop=None):
    global sensor_status, sensor_last_seen

    now = time.time()
    sensors_to_check = list(sensor_last_seen.keys())

    for sensor in sensors_to_check:
        last_seen_time = sensor_last_seen[sensor]

        if now - last_seen_time > timeout_seconds:
            current_state = sensor_status.get(sensor)
            if current_state == "online":
                if loop:
                    asyncio.run_coroutine_threadsafe(update_sensor_status(sensor, "offline"), loop)
                sensor_status[sensor] = "offline"

            if sensor in sensor_last_seen:
                del sensor_last_seen[sensor]
