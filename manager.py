# File manager state sensor
import time
from db import update_sensor_status, get_all_sensor_status

sensor_status = {}

sensor_last_seen = {}


def init():
    """
    Initializes the sensor status and last seen time on startup.

    This function retrieves the status of all sensors from the database.
    For sensors that are 'online', it records the current time as their last seen time.
    """
    global sensor_status, sensor_last_seen

    try:
        sensor_status = get_all_sensor_status()
        now = time.time()
        for sensor, status in sensor_status.items():
            if status == "online":
                sensor_last_seen[sensor] = now

    except Exception as e:
        print(f"Error in init: {e}")


def record_sensor_activity(sensor_name):
    """
    Records the activity of a sensor and updates its status to 'online'.

    This function updates the last seen time for the given sensor.
    If the sensor's current status is not 'online', it updates the status
    in the database and in the local cache.

    Args:
        sensor_name (str): The name of the sensor.
    """

    global sensor_status, sensor_last_seen

    sensor_last_seen[sensor_name] = time.time()

    current_db_status = sensor_status.get(sensor_name)

    if current_db_status != "online":
        try:
            update_sensor_status(sensor_name, "online")
            sensor_status[sensor_name] = "online"
        except Exception as e:
            print(f"Error in record_sensor_activity: {e}")


def check_offline_sensors(timeout_seconds=120):
    """
    Checks for offline sensors and updates their status.

    This function iterates through the list of sensors and checks if their last seen time
    has exceeded the specified timeout. If a sensor is considered offline, its status is
    updated to 'offline' in the database and the local cache, and it is removed from the
    'sensor_last_seen' dictionary.

    Args:
        timeout_seconds (int, optional): The time in seconds after which a sensor is
                                       considered offline. Defaults to 120.
    """
    global sensor_status, sensor_last_seen
    now = time.time()
    sensors_to_check = list(sensor_last_seen.keys())

    for sensor in sensors_to_check:
        last_seen_time = sensor_last_seen[sensor]

        if now - last_seen_time > timeout_seconds:

            current_state = sensor_status.get(sensor)
            if current_state == "online":
                try:
                    update_sensor_status(sensor, "offline")
                    sensor_status[sensor] = "offline"
                except Exception as e:
                    print(f"Error in check_offline_sensors: {e}")

            if sensor in sensor_last_seen:
                del sensor_last_seen[sensor]
