import asyncio
import json
from concurrent.futures import ThreadPoolExecutor

import psycopg2
from psycopg2.extras import RealDictCursor

from app.core import config

executor = ThreadPoolExecutor(max_workers=5)


def _get_db_connection():
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


async def get_db_connection():
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, _get_db_connection)


async def init_db():
    connection = await get_db_connection()
    if connection is None:
        return
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(executor, _init_db_sync, connection)
    finally:
        connection.close()


def _init_db_sync(connection):
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS sensors (
                    sensor_id SERIAL PRIMARY KEY,
                    name VARCHAR(50) UNIQUE,
                    vbat DOUBLE PRECISION,
                    status VARCHAR(100),
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


async def save_message(topic, payload):
    connection = await get_db_connection()
    if connection is None:
        return

    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(executor, _save_message_sync, connection, topic, payload)
    except Exception as e:
        print(f"Error saving message to the database: {e}")
    finally:
        connection.close()


def _save_message_sync(connection, topic, payload):
    try:
        with connection.cursor() as cursor:
            try:
                data = json.loads(payload)
            except Exception as e:
                print(f"Error parsing payload: {e}")
                return

            vbat_value = None
            if "vbat" in data:
                vbat_value = data.pop("vbat")

            cursor.execute(
                "INSERT INTO sensors (name, vbat, status) VALUES (%s, %s, %s) "
                "ON CONFLICT (name) DO UPDATE SET "
                "vbat = COALESCE(EXCLUDED.vbat, sensors.vbat), "
                "status = 'online' "
                "RETURNING sensor_id;",
                (topic, float(vbat_value) if vbat_value else None, "online"),
            )
            row = cursor.fetchone()
            if row is None:
                print(f"Failed to get sensor_id for {topic}")
                return

            sensor_id = row[0]

            for sensor_type, sensor_value in data.items():
                try:
                    float_value = float(sensor_value)
                except (ValueError, TypeError):
                    print(f"Skipping invalid value for {sensor_type}: {sensor_value}")
                    continue

                cursor.execute(
                    "INSERT INTO values (sensor_id, type, value) VALUES (%s, %s, %s);",
                    (sensor_id, sensor_type, float_value),
                )

            connection.commit()
    except Exception as e:
        print(f"Error in _save_message_sync: {e}")
        connection.rollback()


async def update_sensor_status(sensor_name, status):
    connection = await get_db_connection()
    if connection is None:
        return
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(executor, _update_sensor_status_sync, connection, sensor_name, status)
    except Exception as e:
        print(f"Error updating sensor status: {e}")
    finally:
        connection.close()


def _update_sensor_status_sync(connection, sensor_name, status):
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE sensors SET status = %s, updated_at = NOW() WHERE name = %s;",
                (status, sensor_name),
            )
            connection.commit()
    except Exception as e:
        print(f"Error in _update_sensor_status_sync: {e}")


async def get_all_sensor_status() -> dict:
    connection = await get_db_connection()
    if connection is None:
        return {}

    try:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(executor, _get_all_sensor_status_sync, connection)
    except Exception as e:
        print(f"Error getting sensor status: {e}")
        return {}
    finally:
        connection.close()


def _get_all_sensor_status_sync(connection):
    status = {}
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SELECT name, status FROM sensors;")
            result = cursor.fetchall()
            for row in result:
                status[row["name"]] = row["status"]
    except Exception as e:
        print(f"Error in _get_all_sensor_status_sync: {e}")
    return status


async def get_sensors(limit=100):
    connection = await get_db_connection()
    if connection is None:
        return []

    try:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(executor, _get_sensors_sync, connection, limit)
    except Exception as e:
        print(f"Error getting sensors: {e}")
        return []
    finally:
        connection.close()


def _get_sensors_sync(connection, limit):
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """
                SELECT sensor_id, name, vbat, status, updated_at
                FROM sensors
                ORDER BY updated_at DESC
                LIMIT %s;
                """,
                (limit,),
            )
            return cursor.fetchall()
    except Exception as e:
        print(f"Error in _get_sensors_sync: {e}")
        return []


async def get_sensor_values(sensor_name, limit=100):
    connection = await get_db_connection()
    if connection is None:
        return []

    try:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(executor, _get_sensor_values_sync, connection, sensor_name, limit)
    except Exception as e:
        print(f"Error getting sensor values: {e}")
        return []
    finally:
        connection.close()


def _get_sensor_values_sync(connection, sensor_name, limit):
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """
                SELECT s.name, v.type, v.value, v.created_at
                FROM values v
                JOIN sensors s ON s.sensor_id = v.sensor_id
                WHERE s.name = %s
                ORDER BY v.created_at DESC
                LIMIT %s;
                """,
                (sensor_name, limit),
            )
            return cursor.fetchall()
    except Exception as e:
        print(f"Error in _get_sensor_values_sync: {e}")
        return []
