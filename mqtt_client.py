import paho.mqtt.client as mqtt
import config
from db import save_message, update_sensor_status
import manager


def on_connect(client, userdata, flags, rc):
    """
    Callback function for when the client connects to the MQTT broker.

    This function is called when the client receives a CONNACK response from the server.
    It subscribes to the MQTT topic defined in the config file if the connection is successful.

    Args:
        client: The client instance for this callback.
        userdata: The private user data as set in Client() or user_data_set().
        flags: Response flags sent by the broker.
        rc: The connection result.
    """
    if rc == 0:
        print("Connected successfully")
        client.subscribe(config.MQTT_TOPIC)
    else:
        print(f"Connection failed with code {rc}")


def on_message(client, userdata, msg):
    """
    Callback function for when a PUBLISH message is received from the server.

    This function is called when a message is received on a subscribed topic.
    It handles two types of messages:
    - Command messages (topic ends with '/cmd'): Updates the sensor status.
    - Data messages: Records sensor activity and saves the message to the database.

    Args:
        client: The client instance for this callback.
        userdata: The private user data as set in Client() or user_data_set().
        msg: An instance of MQTTMessage. This is a class with members topic, payload, qos, retain.
    """
    # print(f"Topic: {msg.topic}\nMessage: {msg.payload.decode()}")
    if msg.topic.endswith("/cmd"):
        update_sensor_status(msg.topic.rsplit("/", 1)[0], msg.payload.decode().lower())
        manager.sensor_status[msg.topic.rsplit("/", 1)[0]] = (
            msg.payload.decode().lower()
        )
    else:
        sensor_name = msg.topic.rsplit("/", 1)[0]
        payload = msg.payload.decode()
        manager.record_sensor_activity(sensor_name)
        save_message(sensor_name, payload)


def create_mqtt_client():
    """
    Creates and configures an MQTT client.

    This function initializes a Paho MQTT client, sets the username and password if they are
    defined in the config, and assigns the on_connect and on_message callback functions.

    Returns:
        mqtt.Client: A configured MQTT client instance.
    """
    client = mqtt.Client()
    if config.MQTT_USERNAME and config.MQTT_PASSWORD:
        client.username_pw_set(config.MQTT_USERNAME, config.MQTT_PASSWORD)
    client.on_connect = on_connect
    client.on_message = on_message
    return client
