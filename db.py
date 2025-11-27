import psycopg2
from psycopg2.extras import RealDictCursor
import config
import json


def get_db_connection():
    """
    Establishes and returns a connection to the PostgreSQL database.

    Uses the connection parameters defined in the 'config' module.

    Returns:
        psycopg2.connection: A connection object to the database, or None if the connection fails.
    """
    try:
        connection = psycopg2.connect(
            host=config.DB_HOST,
            port=config.DB_PORT,
            database=config.DB_NAME,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
        )
        return connection
    except Exception as e:
        print(f"Error connecting to the database: {e}")
        return None


def init_db():
    """
    Initializes the database by creating the necessary tables.

    This function creates the 'sensors' and 'values' tables if they do not already exist,
    along with their respective indexes.
    """
    connection = get_db_connection()
    if connection is None:
        return
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS sensors (
                    sensor_id SERIAL PRIMARY KEY,
                    name VARCHAR(50) UNIQUE,
                    vbat DOUBLE PRECISION,
                    status VARCHAR(20),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS values (
                    id BIGSERIAL PRIMARY KEY,
                    sensor_id INT REFERENCES sensors(sensor_id),
                    type VARCHAR(20),
                    value DOUBLE PRECISION,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_type_time ON values(type, created_at);
            """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_sensor_value ON values(sensor_id, value);
            """
            )
            connection.commit()
    except Exception as e:
        print(f"Error initializing the database: {e}")
    finally:
        connection.close()


def save_message(topic, payload):
    """
    Saves a message from a sensor to the database.

    This function checks if the sensor with the given topic name exists in the 'sensors' table.
    If not, it creates a new sensor entry. It then parses the JSON payload and inserts the
    sensor data into the 'values' table. If the payload contains a 'vbat' key, it updates
    the battery voltage for the sensor in the 'sensors' table.

    Args:
        topic (str): The MQTT topic, which is used as the sensor name.
        payload (str): The JSON-formatted string containing sensor data.
    """
    connection = get_db_connection()
    if connection is None:
        return
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT sensor_id FROM sensors WHERE name = %s;", (topic,))
            result = cursor.fetchone()

            if result is None:
                cursor.execute(
                    "INSERT INTO sensors (name, status) VALUES (%s, %s) RETURNING sensor_id;",
                    (topic, "offline"),
                )
                sensor_id = cursor.fetchone()[0]
            else:
                sensor_id = result[0]

            try:
                data = json.loads(payload)

                if "vbat" in data:
                    vbat_value = data.pop("vbat")
                    cursor.execute(
                        "UPDATE sensors SET vbat = %s, updated_at = NOW() WHERE sensor_id = %s;",
                        (float(vbat_value), sensor_id),
                    )

                for sensor_type, sensor_value in data.items():
                    cursor.execute(
                        "INSERT INTO values (sensor_id, type, value) VALUES (%s, %s, %s);",
                        (sensor_id, sensor_type, float(sensor_value)),
                    )
            except Exception as e:
                print(f"Error parsing payload: {e}")
                return
            connection.commit()
    except Exception as e:
        print(f"Error saving message to the database: {e}")
    finally:
        connection.close()


def update_sensor_status(sensor_name, status):
    """
    Updates the status of a sensor in the database.

    Args:
        sensor_name (str): The name of the sensor to update.
        status (str): The new status for the sensor.
    """
    connection = get_db_connection()
    if connection is None:
        return
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE sensors SET status = %s, updated_at = NOW() WHERE name = %s;",
                (status, sensor_name),
            )
            connection.commit()
    except Exception as e:
        print(f"Error updating sensor status: {e}")
    finally:
        connection.close()


def get_all_sensor_status() -> dict:
    """
    Retrieves the status of all sensors from the database.

    Returns:
        dict: A dictionary where keys are sensor names and values are their statuses.
              Returns an empty dictionary if the database connection fails or if there are no sensors.
    """
    connection = get_db_connection()
    if connection is None:
        return {}

    status = {}

    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SELECT name, status FROM sensors;")
            result = cursor.fetchall()
            for row in result:
                status[row["name"]] = row["status"]
    except Exception as e:
        print(f"Error getting sensor status: {e}")
    finally:
        connection.close()
    return status
