import psycopg2
from psycopg2.extras import RealDictCursor
import config
import json
import sender_service
import asyncio
from concurrent.futures import ThreadPoolExecutor

sender = sender_service.DataSyncService()
executor = ThreadPoolExecutor(max_workers=5)

def _get_db_connection():
    """Synchronous helper for database connections."""
    try:
        connection = psycopg2.connect(
            host=config.DB_HOST,
            port=config.DB_PORT,
            database=config.DB_NAME,
            user=config.DB_USER,
            password=config.DB_PASSWORD
        )
        return connection
    except Exception as e:
        print(f"Error connecting to the database: {e}")
        return None

async def get_db_connection():
    """Asynchronous database connection wrapper."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, _get_db_connection)

async def init_db():
    """Initializes the database asynchronously."""
    connection = await get_db_connection()
    if connection is None:
        return
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(executor, _init_db_sync, connection)
    finally:
        connection.close()

def _init_db_sync(connection):
    """Synchronous database initialization."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sensors (
                    sensor_id SERIAL PRIMARY KEY,
                    name VARCHAR(50) UNIQUE,
                    vbat DOUBLE PRECISION,
                    status VARCHAR(100),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS values (
                    id BIGSERIAL PRIMARY KEY,
                    sensor_id INT REFERENCES sensors(sensor_id),
                    type VARCHAR(20),
                    value DOUBLE PRECISION,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_type_time ON values(type, created_at);
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_sensor_value ON values(sensor_id, value);
            """)
            connection.commit()
    except Exception as e:
        print(f"Error initializing the database: {e}")

async def save_message(topic, payload):
    """Saves a message from a sensor to the database asynchronously."""
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
    """Synchronous message saving with blocking gRPC calls."""
    try:
        with connection.cursor() as cursor:
            try:
                data = json.loads(payload)
            except Exception as e:
                print(f"Error parsing payload: {e}")
                return
            
            vbat_value = None
            if 'vbat' in data:
                vbat_value = data.pop('vbat')
            
            cursor.execute("SELECT sensor_id FROM sensors WHERE name = %s;", (topic,))
            existing = cursor.fetchone()
            is_new_sensor = existing is None
            
            cursor.execute(
                "INSERT INTO sensors (name, vbat, status) VALUES (%s, %s, %s) "
                "ON CONFLICT (name) DO UPDATE SET "
                "vbat = COALESCE(EXCLUDED.vbat, sensors.vbat), "
                "status = 'online' "
                "RETURNING sensor_id;",
                (topic, float(vbat_value) if vbat_value else None, 'online')
            )
            row = cursor.fetchone()
            if row is None:
                print(f"Failed to get sensor_id for {topic}")
                return
            
            sensor_id = row[0]

            if is_new_sensor:
                try:
                    sender.UploadSensor(name=topic, vbat=float(vbat_value) if vbat_value else 0.0, status='online')
                except Exception as e:
                    print(f"Error uploading sensor {topic}: {e}")

            for sensor_type, sensor_value in data.items():
                try:
                    float_value = float(sensor_value)
                except (ValueError, TypeError):
                    print(f"Skipping invalid value for {sensor_type}: {sensor_value}")
                    continue
                
                cursor.execute(
                    "INSERT INTO values (sensor_id, type, value) VALUES (%s, %s, %s) RETURNING created_at;",
                    (sensor_id, sensor_type, float_value)
                )
                result = cursor.fetchone()
                created_at = result[0] if result else None
                
                try:
                    sender.UploadSingleRow(sensor_id, sensor_type, float_value, created_at)
                except Exception as e:
                    print(f"Error uploading data row for sensor {topic}: {e}")
            
            connection.commit()
    except Exception as e:
        print(f"Error in _save_message_sync: {e}")
        connection.rollback()

async def update_sensor_status(sensor_name, status):
    """Updates sensor status asynchronously."""
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
    """Synchronous sensor status update."""
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE sensors SET status = %s, updated_at = NOW() WHERE name = %s;",
                (status, sensor_name)
            )
            connection.commit()
    except Exception as e:
        print(f"Error in _update_sensor_status_sync: {e}")

async def get_all_sensor_status() -> dict:
    """Retrieves all sensor statuses asynchronously."""
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
    """Synchronous sensor status retrieval."""
    status = {}
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SELECT name, status FROM sensors;")
            result = cursor.fetchall()
            for row in result:
                status[row['name']] = row['status']
    except Exception as e:
        print(f"Error in _get_all_sensor_status_sync: {e}")
    return status