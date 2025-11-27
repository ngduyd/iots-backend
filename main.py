import config
import db
from mqtt_client import create_mqtt_client
import time
import manager

SENSOR_OFFLINE_TIMEOUT = 120


def main():
    time.sleep(5)
    try:
        print("Initializing database...")
        db.init_db()
        print("Database initialized successfully")
        client = create_mqtt_client()
        print("Connecting to MQTT broker...")
        client.connect(config.MQTT_BROKER, config.MQTT_PORT, 60)
        print("Connected to MQTT broker, starting loop...")
        # client.loop_forever()
        client.loop_start()
        while True:
            time.sleep(1)
            try:
                manager.check_offline_sensors(SENSOR_OFFLINE_TIMEOUT)
            except Exception as e:
                print(f"Error in main: {e}")
    except KeyboardInterrupt:
        print("Exiting...")
    except Exception as e:
        print(f"Error in main: {e}")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
