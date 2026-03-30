import asyncio
import hashlib
import json
import os
import time
import uuid
import asyncpg
from app.core import config
from datetime import datetime

db_pool = None
_pool_lock = asyncio.Lock()

DEFAULT_THRESHOLDS = {
    "co2": {"min": config.DEFAULT_CO2_MIN, "max": config.DEFAULT_CO2_MAX, "activated": True},
    "temp": {"min": config.DEFAULT_TEMP_MIN, "max": config.DEFAULT_TEMP_MAX, "activated": True},
    "rh": {"min": config.DEFAULT_HUMID_MIN, "max": config.DEFAULT_HUMID_MAX, "activated": True},
    "pm2_5": {"min": config.DEFAULT_PM25_MIN, "max": config.DEFAULT_PM25_MAX, "activated": True},
    "pm10": {"min": config.DEFAULT_PM10_MIN, "max": config.DEFAULT_PM10_MAX, "activated": True},
}


async def _init_connection(connection):
    await connection.set_type_codec(
        "json",
        schema="pg_catalog",
        encoder=json.dumps,
        decoder=json.loads,
        format="text",
    )
    await connection.set_type_codec(
        "jsonb",
        schema="pg_catalog",
        encoder=json.dumps,
        decoder=json.loads,
        format="text",
    )


async def get_db_pool():
    global db_pool

    if db_pool is not None:
        return db_pool

    async with _pool_lock:
        if db_pool is not None:
            return db_pool

        try:
            db_pool = await asyncpg.create_pool(
                host=config.DB_HOST,
                port=config.DB_PORT,
                database=config.DB_NAME,
                user=config.DB_USER,
                password=config.DB_PASSWORD,
                min_size=1,
                max_size=10,
                init=_init_connection,
            )
            return db_pool
        except Exception as e:
            print(f"Error connecting to the database: {e}")
            return None


async def close_db():
    global db_pool

    if db_pool is not None:
        await db_pool.close()
        db_pool = None


async def _execute(query, *args):
    pool = await get_db_pool()
    if pool is None:
        return None

    async with pool.acquire() as connection:
        return await connection.execute(query, *args)


async def _fetch(query, *args):
    pool = await get_db_pool()
    if pool is None:
        return []

    async with pool.acquire() as connection:
        lock_timeout_ms = max(1, config.DB_READ_LOCK_TIMEOUT_MS)
        statement_timeout_ms = max(1, config.DB_READ_STATEMENT_TIMEOUT_MS)
        async with connection.transaction(readonly=True, isolation="read_committed"):
            await connection.execute(f"SET LOCAL lock_timeout = '{lock_timeout_ms}ms';")
            await connection.execute(f"SET LOCAL statement_timeout = '{statement_timeout_ms}ms';")
            rows = await connection.fetch(query, *args)
            return [dict(row) for row in rows]


async def _fetchrow(query, *args):
    pool = await get_db_pool()
    if pool is None:
        return None

    async with pool.acquire() as connection:
        normalized = query.lstrip().upper()
        if normalized.startswith("SELECT"):
            lock_timeout_ms = max(1, config.DB_READ_LOCK_TIMEOUT_MS)
            statement_timeout_ms = max(1, config.DB_READ_STATEMENT_TIMEOUT_MS)
            async with connection.transaction(readonly=True, isolation="read_committed"):
                await connection.execute(f"SET LOCAL lock_timeout = '{lock_timeout_ms}ms';")
                await connection.execute(f"SET LOCAL statement_timeout = '{statement_timeout_ms}ms';")
                row = await connection.fetchrow(query, *args)
                return dict(row) if row else None

        row = await connection.fetchrow(query, *args)
        return dict(row) if row else None


async def init_db():
    pool = await get_db_pool()
    if pool is None:
        return

    try:
        async with pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS groups (
                        group_id SERIAL PRIMARY KEY,
                        name VARCHAR(100) NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    """
                )
                await connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS branches (
                        branch_id SERIAL PRIMARY KEY,
                        group_id INT REFERENCES groups(group_id),
                        name VARCHAR(100) NOT NULL,
                        thresholds JSONB,
                        model_id UUID REFERENCES models(model_id) ON DELETE SET NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    """
                )
                await connection.execute(
                    """
                    ALTER TABLE branches ADD COLUMN IF NOT EXISTS thresholds JSONB;
                    """
                )
                await connection.execute(
                    """
                    DO $$
                    BEGIN
                        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='branches' AND column_name='metadata') THEN
                            ALTER TABLE branches RENAME COLUMN metadata TO thresholds;
                        END IF;
                    END $$;
                    """
                )
                await connection.execute(
                    """
                    ALTER TABLE branches
                    ADD COLUMN IF NOT EXISTS model_id UUID REFERENCES models(model_id) ON DELETE SET NULL;
                    """
                )
                await connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS alerts (
                        alert_id SERIAL PRIMARY KEY,
                        branch_id INT REFERENCES branches(branch_id) ON DELETE CASCADE,
                        message TEXT NOT NULL,
                        level VARCHAR(50) NOT NULL,
                        is_read BOOLEAN NOT NULL DEFAULT FALSE,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    """
                )
                await connection.execute(
                    """
                    ALTER TABLE alerts
                    ADD COLUMN IF NOT EXISTS is_read BOOLEAN NOT NULL DEFAULT FALSE;
                    """
                )
                await connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS users (
                        user_id SERIAL PRIMARY KEY,
                        group_id INT REFERENCES groups(group_id),
                        username VARCHAR(50) UNIQUE NOT NULL,
                        password_hash VARCHAR(255) NOT NULL,
                        role VARCHAR(20) DEFAULT 'user' NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    """
                )
                await connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_sessions (
                        session_id VARCHAR(128) PRIMARY KEY,
                        user_id INT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                        ip_address VARCHAR(45),
                        user_agent TEXT,
                        is_active BOOLEAN NOT NULL DEFAULT TRUE,
                        expires_at TIMESTAMPTZ NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    """
                )
                await connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS sensors (
                        sensor_id VARCHAR(32) PRIMARY KEY,
                        branch_id INT REFERENCES branches(branch_id),
                        name VARCHAR(50),
                        status VARCHAR(100) DEFAULT 'offline' NOT NULL,
                        deleted_at TIMESTAMPTZ,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    """
                )
                await connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS jobs (
                        job_id UUID PRIMARY KEY,
                        branch_id INT REFERENCES branches(branch_id) ON DELETE CASCADE,
                        user_id INT REFERENCES users(user_id) ON DELETE SET NULL,
                        secret VARCHAR(255) NOT NULL,
                        dataset_params JSONB,
                        feature_engineering_params JSONB,
                        forecast_params JSONB,
                        model_hyperparams JSONB,
                        status VARCHAR(50) DEFAULT 'pending' NOT NULL,
                        message TEXT,
                        result JSONB,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    """
                )
                await connection.execute(
                    """
                    ALTER TABLE sensors
                    ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;
                    """
                )
                await connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS values (
                        id BIGSERIAL PRIMARY KEY,
                        sensor_id VARCHAR(32) REFERENCES sensors(sensor_id),
                        value JSONB NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    """
                )
                await connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS cameras (
                        camera_id VARCHAR(32) PRIMARY KEY,
                        branch_id INT REFERENCES branches(branch_id),
                        name VARCHAR(50),
                        secret VARCHAR(64),
                        activate BOOLEAN NOT NULL DEFAULT FALSE,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    """
                )
                await connection.execute(
                    """
                    ALTER TABLE jobs
                    ADD COLUMN IF NOT EXISTS message TEXT;
                    """
                )
                await connection.execute(
                    """
                    ALTER TABLE cameras
                    ADD COLUMN IF NOT EXISTS activate BOOLEAN NOT NULL DEFAULT FALSE;
                    """
                )
                await connection.execute(
                    """
                    ALTER TABLE cameras
                    ADD COLUMN IF NOT EXISTS status VARCHAR(100) DEFAULT 'offline' NOT NULL;
                    """
                )
                await connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS camera_access_requests (
                        request_id SERIAL PRIMARY KEY,
                        camera_id VARCHAR(32) REFERENCES cameras(camera_id) ON DELETE CASCADE,
                        user_id INT REFERENCES users(user_id) ON DELETE CASCADE,
                        status VARCHAR(20) DEFAULT 'pending' NOT NULL,
                        access_token VARCHAR(128),
                        expires_at TIMESTAMPTZ,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    """
                )
                await connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS image_analysis (
                        image_id VARCHAR(64) PRIMARY KEY,
                        camera_id VARCHAR(32) REFERENCES cameras(camera_id) ON DELETE SET NULL,
                        image_path VARCHAR(255),
                        people_count INT DEFAULT 0,
                        metadata JSONB,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    """
                )
                await connection.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_sensor_time_desc ON values(sensor_id, created_at DESC);
                    """
                )
                await connection.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id);
                    """
                )
                await connection.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_user_sessions_expires_at ON user_sessions(expires_at);
                    """
                )
                await connection.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_sensors_active_branch_updated
                    ON sensors(branch_id, updated_at)
                    WHERE deleted_at IS NULL;
                    """
                )
                await connection.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_sensors_active_updated
                    ON sensors(updated_at)
                    WHERE deleted_at IS NULL;
                    """
                )
                await connection.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_camera_access_requests_token
                    ON camera_access_requests(access_token);
                    """
                )
                await connection.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_image_analysis_camera ON image_analysis(camera_id);
                    """
                )
                await connection.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_image_analysis_created ON image_analysis(created_at DESC);
                    """
                )
                await connection.execute(
                    """
                    CREATE OR REPLACE FUNCTION sync_sensor_status_from_value()
                    RETURNS TRIGGER AS $$
                    BEGIN
                        UPDATE sensors
                        SET status = 'online',
                            updated_at = NOW()
                        WHERE sensor_id = NEW.sensor_id
                          AND deleted_at IS NULL
                          AND status IS DISTINCT FROM 'online';

                        RETURN NEW;
                    END;
                    $$ LANGUAGE plpgsql;
                    """
                )
                await connection.execute(
                    """
                    DROP TRIGGER IF EXISTS trg_sync_sensor_status_from_value ON values;
                    """
                )
                await connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS models (
                        model_id UUID PRIMARY KEY,
                        group_id INT REFERENCES groups(group_id) ON DELETE CASCADE,
                        name VARCHAR(255) NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        deleted_at TIMESTAMPTZ
                    );
                    """
                )
                await connection.execute(
                    """
                    ALTER TABLE models ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;
                    """
                )
                await connection.execute(
                    """
                    ALTER TABLE jobs
                    ADD COLUMN IF NOT EXISTS model_id UUID REFERENCES models(model_id);
                    """
                )
                await connection.execute(
                    """
                    CREATE TRIGGER trg_sync_sensor_status_from_value
                    AFTER INSERT ON values
                    FOR EACH ROW
                    EXECUTE FUNCTION sync_sensor_status_from_value();
                    """
                )
                await connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS logs (
                        log_id SERIAL PRIMARY KEY,
                        user_id INT REFERENCES users(user_id) ON DELETE SET NULL,
                        group_id INT REFERENCES groups(group_id) ON DELETE CASCADE,
                        action VARCHAR(50) NOT NULL,
                        target_type VARCHAR(50),
                        target_id VARCHAR(128),
                        message TEXT,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    """
                )
                await connection.execute(
                    """
                    DO $$
                    BEGIN
                        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='logs' AND column_name='details') THEN
                            ALTER TABLE logs RENAME COLUMN details TO message;
                            ALTER TABLE logs ALTER COLUMN message TYPE TEXT USING message::text;
                        END IF;
                    END $$;
                    """
                )
                await connection.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_logs_group_id ON logs(group_id);
                    """
                )
                await connection.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_logs_created_at ON logs(created_at DESC);
                    """
                )
    except Exception as e:
        print(f"Error initializing the database: {e}")


async def save_message(topic, payload, received_at=None):
    try:
        data = json.loads(payload)
    except Exception as e:
        print(f"Error parsing payload: {e}")
        return

    try:
        if received_at is not None:
            await _execute(
                "INSERT INTO values (sensor_id, value, created_at) VALUES ($1, $2::jsonb, $3);",
                topic,
                json.dumps(data),
                received_at,
            )
        else:
            await _execute(
                "INSERT INTO values (sensor_id, value) VALUES ($1, $2::jsonb);",
                topic,
                json.dumps(data),
            )
    except Exception as e:
        print(f"Error saving message to the database: {e}")


async def save_messages_batch(items):
    """Persist multiple MQTT messages in one DB roundtrip.

    Args:
        items: list of tuples (sensor_id, payload_str, received_at)
    """
    if not items:
        return

    pool = await get_db_pool()
    if pool is None:
        return

    values = []
    for sensor_id, payload, received_at in items:
        if not sensor_id:
            continue
        try:
            parsed = json.loads(payload)
        except Exception:
            continue
        values.append((sensor_id, json.dumps(parsed), received_at))

    if not values:
        return

    try:
        async with pool.acquire() as connection:
            await connection.executemany(
                """
                INSERT INTO values (sensor_id, value, created_at)
                VALUES ($1, $2::jsonb, $3);
                """,
                values,
            )
    except Exception as e:
        print(f"Error saving message batch to the database: {e}")


async def update_sensor_status(sensor_id, status):
    try:
        await _execute(
            "UPDATE sensors SET status = $1, updated_at = NOW() WHERE sensor_id = $2 AND deleted_at IS NULL;",
            status,
            sensor_id,
        )
    except Exception as e:
        print(f"Error updating sensor status: {e}")


async def update_camera_status(camera_id, status):
    try:
        await _execute(
            "UPDATE cameras SET status = $1 WHERE camera_id = $2;",
            status,
            camera_id,
        )
    except Exception as e:
        print(f"Error updating camera status: {e}")


async def get_all_sensor_status() -> dict:
    try:
        rows = await _fetch("SELECT sensor_id, status FROM sensors WHERE deleted_at IS NULL;")
        return {row["sensor_id"]: row["status"] for row in rows}
    except Exception as e:
        print(f"Error getting sensor status: {e}")
        return {}


async def get_sensors(limit=100, group_id=None):
    try:
        if group_id is not None:
            return await _fetch(
                """
                SELECT s.sensor_id, s.name, s.status, s.updated_at
                FROM sensors s
                JOIN branches b ON b.branch_id = s.branch_id
                WHERE b.group_id = $1
                  AND s.deleted_at IS NULL
                ORDER BY s.updated_at DESC
                LIMIT $2;
                """,
                group_id,
                limit,
            )

        return await _fetch(
                """
            SELECT sensor_id, name, status, updated_at
            FROM sensors
            WHERE deleted_at IS NULL
            ORDER BY updated_at DESC
            LIMIT $1;
            """,
            limit,
        )
    except Exception as e:
        print(f"Error getting sensors: {e}")
        return []


async def get_sensor(sensor_id, group_id=None):
    try:
        if group_id is not None:
            return await _fetchrow(
                """
                SELECT s.sensor_id, s.name, s.branch_id, s.status, s.updated_at
                FROM sensors s
                JOIN branches b ON b.branch_id = s.branch_id
                WHERE s.sensor_id = $1 AND b.group_id = $2 AND s.deleted_at IS NULL;
                """,
                sensor_id,
                group_id,
            )

        return await _fetchrow(
            """
            SELECT sensor_id, name, branch_id, status, updated_at
            FROM sensors
            WHERE sensor_id = $1 AND deleted_at IS NULL;
            """,
            sensor_id,
        )
    except Exception as e:
        print(f"Error getting sensor: {e}")
        return None


async def get_sensors_by_branch(branch_id, limit=100):
    try:
        return await _fetch(
            """
            SELECT sensor_id, name, status, updated_at
            FROM sensors
            WHERE branch_id = $1 AND deleted_at IS NULL
            ORDER BY updated_at DESC
            LIMIT $2;
            """,
            branch_id,
            limit,
        )
    except Exception as e:
        print(f"Error getting sensors by branch: {e}")
        return []


async def get_cameras_by_branch(branch_id, limit=100):
    try:
        return await _fetch(
            """
            SELECT camera_id, branch_id, name, secret, created_at, status
            FROM cameras
            WHERE branch_id = $1
            ORDER BY created_at DESC
            LIMIT $2;
            """,
            branch_id,
            limit,
        )
    except Exception as e:
        print(f"Error getting cameras by branch: {e}")
        return []


async def get_camera_by_branch(branch_id):
    try:
        return await _fetchrow(
            """
            SELECT camera_id, branch_id, name, status, created_at
            FROM cameras
            WHERE branch_id = $1
            LIMIT 1;
            """,
            branch_id,
        )
    except Exception as e:
        print(f"Error getting camera by branch {branch_id}: {e}")
        return None


async def get_sensor_values(sensor_id, limit=1000000, group_id=None, from_time: datetime | None = None, to_time: datetime | None = None):
    try:
        val_where = ["v.sensor_id = $1"]
        params = [sensor_id]

        if from_time is not None:
            val_where.append(f"v.created_at >= ${len(params) + 1}")
            params.append(from_time)

        if to_time is not None:
            val_where.append(f"v.created_at <= ${len(params) + 1}")
            params.append(to_time)

        limit_idx = len(params) + 1
        params.append(limit)

        if group_id is not None:
            group_idx = len(params) + 1
            params.append(group_id)
            query = f"""
                SELECT v.sensor_id, v.value, v.created_at
                FROM values v
                JOIN sensors s ON s.sensor_id = v.sensor_id
                JOIN branches b ON b.branch_id = s.branch_id
                WHERE {' AND '.join(val_where)}
                  AND s.deleted_at IS NULL
                  AND b.group_id = ${group_idx}
                ORDER BY v.created_at DESC
                LIMIT ${limit_idx};
            """
        else:
            query = f"""
                SELECT v.sensor_id, v.value, v.created_at
                FROM values v
                JOIN sensors s ON s.sensor_id = v.sensor_id
                WHERE {' AND '.join(val_where)}
                  AND s.deleted_at IS NULL
                ORDER BY v.created_at DESC
                LIMIT ${limit_idx};
            """

        return await _fetch(query, *params)
    except Exception as e:
        print(f"Error getting sensor values: {e}")
        return []


async def add_sensor(sensor_name=None, branch_id=None):
    if branch_id is None:
        print("branch_id is required")
        return None

    try:
        sensor_id = _generate_sensor_id()
        return await _fetchrow(
            """
            INSERT INTO sensors (sensor_id, name, branch_id)
            VALUES ($1, $2, $3)
            RETURNING sensor_id, name, status, updated_at;
            """,
            sensor_id,
            sensor_name,
            branch_id,
        )
    except Exception as e:
        print(f"Error adding sensor: {e}")
        return None


async def get_branch_data_for_export(branch_id: int, from_time: datetime, to_time: datetime):
    """Fetch all values for all sensors in a branch, plus people count history for CSV export."""
    try:
        sensor_values = await _fetch(
            """
            SELECT v.sensor_id, s.name as sensor_name, v.value, v.created_at
            FROM values v
            JOIN sensors s ON s.sensor_id = v.sensor_id
            WHERE s.branch_id = $1 
              AND s.deleted_at IS NULL
              AND v.created_at >= $2
              AND v.created_at <= $3
            ORDER BY v.created_at ASC;
            """,
            branch_id,
            from_time,
            to_time,
        )

        people_counts = await _fetch(
            """
            SELECT ia.people_count, ia.created_at
            FROM image_analysis ia
            JOIN cameras c ON c.camera_id = ia.camera_id
            WHERE c.branch_id = $1
              AND ia.created_at >= $2
              AND ia.created_at <= $3
            ORDER BY ia.created_at ASC;
            """,
            branch_id,
            from_time,
            to_time,
        )

        return sensor_values, people_counts
    except Exception as e:
        print(f"Error getting branch data for export: {e}")
        return [], []



async def update_sensor(sensor_id, sensor_name=None, branch_id=None, delete=False):
    try:
        if delete:
            return await _fetchrow(
                """
                UPDATE sensors
                SET deleted_at = NOW(), updated_at = NOW()
                WHERE sensor_id = $1 AND deleted_at IS NULL
                RETURNING sensor_id, name, status, updated_at;
                """,
                sensor_id,
            )

        return await _fetchrow(
            """
            UPDATE sensors
            SET name = $1, branch_id = $2, updated_at = NOW()
            WHERE sensor_id = $3 AND deleted_at IS NULL
            RETURNING sensor_id, name, status, updated_at;
            """,
            sensor_name,
            branch_id,
            sensor_id,
        )
    except Exception as e:
        print(f"Error updating sensor: {e}")
        return None


def _generate_sensor_id():
    ts = int(time.time()).to_bytes(4, "big")
    rand = os.urandom(12)
    return (ts + rand).hex()


def _generate_camera_id():
    ts = int(time.time()).to_bytes(4, "big")
    rand = os.urandom(12)
    return (ts + rand).hex()


def _generate_camera_secret():
    return os.urandom(32).hex()


async def get_latest_people_count_by_branch(branch_id: int):
    """Return the people_count history from the last 10 minutes for any online camera in the branch."""
    try:
        return await _fetch(
            """
            SELECT ia.people_count, ia.created_at, ia.camera_id
            FROM image_analysis ia
            JOIN cameras c ON c.camera_id = ia.camera_id
            WHERE c.branch_id = $1
              AND c.status = 'online'
              AND ia.created_at >= NOW() - INTERVAL '11 minutes'
            ORDER BY ia.created_at DESC;
            """,
            branch_id,
        )
    except Exception as e:
        print(f"Error getting latest people count for branch {branch_id}: {e}")
        return []

async def get_sensor_name(sensor_id):
    try:
        row = await _fetchrow("SELECT name FROM sensors WHERE sensor_id = $1 AND deleted_at IS NULL;", sensor_id)
        return row["name"] if row else sensor_id
    except Exception as e:
        print(f"Error getting sensor name: {e}")
        return sensor_id

async def create_log(user_id, action, group_id=None, target_type=None, target_id=None, message=None):
    try:
        query = """
            INSERT INTO logs (user_id, group_id, action, target_type, target_id, message)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING log_id;
        """
        return await _fetchrow(query, user_id, group_id, action, target_type, target_id, message)
    except Exception as e:
        print(f"Error creating log: {e}")
        return None

async def get_logs(limit=100, offset=0, group_id=None, action=None, target_type=None, from_date=None, to_date=None):
    try:
        where_clauses = []
        params = []
        
        if group_id is not None:
            params.append(group_id)
            where_clauses.append(f"l.group_id = ${len(params)}")
            
        if action:
            params.append(action)
            where_clauses.append(f"l.action = ${len(params)}")
            
        if target_type:
            params.append(target_type)
            where_clauses.append(f"l.target_type = ${len(params)}")
            
        if from_date:
            params.append(from_date)
            where_clauses.append(f"l.created_at >= ${len(params)}")
            
        if to_date:
            params.append(to_date)
            where_clauses.append(f"l.created_at <= ${len(params)}")
            
        where_str = ""
        if where_clauses:
            where_str = "WHERE " + " AND ".join(where_clauses)
            
        params.append(limit)
        limit_idx = len(params)
        params.append(offset)
        offset_idx = len(params)
        
        query = f"""
            SELECT l.*, u.username
            FROM logs l
            LEFT JOIN users u ON l.user_id = u.user_id
            {where_str}
            ORDER BY l.created_at DESC
            LIMIT ${limit_idx} OFFSET ${offset_idx};
        """
        return await _fetch(query, *params)
    except Exception as e:
        print(f"Error getting logs: {e}")
        return []
    try:
        row = await _fetchrow(
            """
            SELECT name FROM sensors WHERE sensor_id = $1 AND deleted_at IS NULL;
            """,
            sensor_id,
        )
        return row["name"] if row else None
    except Exception as e:
        print(f"Error getting sensor name: {e}")
        return None


async def get_cameras(limit=100, group_id=None):
    try:
        if group_id is not None:
            return await _fetch(
                """
                SELECT c.camera_id, c.branch_id, c.name, c.secret, c.activate, c.created_at, c.status
                FROM cameras c
                JOIN branches b ON b.branch_id = c.branch_id
                WHERE b.group_id = $1
                ORDER BY c.camera_id DESC
                LIMIT $2;
                """,
                group_id,
                limit,
            )

        return await _fetch(
            """
            SELECT camera_id, branch_id, name, secret, activate, created_at, status
            FROM cameras
            ORDER BY camera_id DESC
            LIMIT $1;
            """,
            limit,
        )
    except Exception as e:
        print(f"Error getting cameras: {e}")
        return []


async def get_active_cameras():
    try:
        return await _fetch(
            """
            SELECT camera_id, branch_id, name, secret, activate, created_at, status
            FROM cameras
            WHERE activate = TRUE
            ORDER BY camera_id DESC;
            """
        )
    except Exception as e:
        print(f"Error getting active cameras: {e}")
        return []


async def get_camera(camera_id, group_id=None):
    try:
        if group_id is not None:
            return await _fetchrow(
                """
                SELECT c.camera_id, c.branch_id, c.name, c.secret, c.activate, c.created_at, c.status
                FROM cameras c
                JOIN branches b ON b.branch_id = c.branch_id
                WHERE c.camera_id = $1 AND b.group_id = $2;
                """,
                camera_id,
                group_id,
            )

        return await _fetchrow(
            """
            SELECT camera_id, branch_id, name, secret, activate, created_at, status
            FROM cameras
            WHERE camera_id = $1;
            """,
            camera_id,
        )
    except Exception as e:
        print(f"Error getting camera: {e}")
        return None


async def create_camera_access_request(camera_id, user_id, ttl_seconds=60):
    try:
        access_token = os.urandom(24).hex()
        return await _fetchrow(
            """
            INSERT INTO camera_access_requests (camera_id, user_id, access_token, status, expires_at, updated_at)
            VALUES ($1, $2, $3, 'approved', NOW() + ($4 * INTERVAL '1 second'), NOW())
            RETURNING request_id, camera_id, user_id, access_token, status, expires_at, created_at;
            """,
            camera_id,
            user_id,
            access_token,
            ttl_seconds,
        )
    except Exception as e:
        print(f"Error creating camera access request: {e}")
        return None


async def verify_camera_access_request_by_token(access_token, ttl_seconds=60):
    """Verify camera access token and extend expiry on every successful access."""
    try:
        return await _fetchrow(
            """
                        WITH candidate AS (
                                SELECT request_id
                                FROM camera_access_requests
                                WHERE access_token = $1
                                    AND status IN ('approved', 'used')
                                    AND expires_at > NOW()
                                ORDER BY request_id DESC
                                LIMIT 1
                        )
                        UPDATE camera_access_requests car
                        SET status = 'used',
                            expires_at = NOW() + ($2 * INTERVAL '1 second'),
                            updated_at = NOW()
                        FROM candidate
                        WHERE car.request_id = candidate.request_id
                        RETURNING car.request_id, car.camera_id, car.user_id, car.access_token, car.status, car.expires_at, car.created_at;
            """,
            access_token,
            ttl_seconds,
        )
    except Exception as e:
        print(f"Error verifying camera access request by token: {e}")
        return None


async def verify_camera_access_request(camera_id, access_token, user_id):
    try:
        return await _fetchrow(
            """
                        WITH candidate AS (
                                SELECT request_id
                                FROM camera_access_requests
                                WHERE camera_id = $1
                                    AND access_token = $2
                                    AND user_id = $3
                                    AND status = 'approved'
                                    AND expires_at > NOW()
                                ORDER BY request_id DESC
                                LIMIT 1
                        )
                        UPDATE camera_access_requests car
                        SET status = 'used', updated_at = NOW()
                        FROM candidate
                        WHERE car.request_id = candidate.request_id
                        RETURNING car.request_id, car.camera_id, car.user_id, car.access_token, car.status, car.expires_at, car.created_at;
            """,
            camera_id,
            access_token,
            user_id,
        )
    except Exception as e:
        print(f"Error verifying camera access request: {e}")
        return None


async def verify_camera_stream(camera_id, secret):
    try:
        return await _fetchrow(
            """
            UPDATE cameras
            SET status = 'online'
            WHERE camera_id = $1 AND secret = $2
            RETURNING camera_id, branch_id, name;
            """,
            camera_id,
            secret,
        )
    except Exception as e:
        print(f"Error verifying camera stream: {e}")
        return None


async def end_camera_stream(camera_id, secret):
    try:
        return await _fetchrow(
            """
            UPDATE cameras
            SET status = 'offline'
            WHERE camera_id = $1 AND secret = $2
            RETURNING camera_id, branch_id, name;
            """,
            camera_id,
            secret,
        )
    except Exception as e:
        print(f"Error ending camera stream: {e}")
        return None


async def reset_all_cameras_offline():
    """Reset all cameras to 'offline' on server startup."""
    try:
        await _execute("UPDATE cameras SET status = 'offline';")
        print("[STARTUP] All cameras reset to offline")
    except Exception as e:
        print(f"[STARTUP] Error resetting camera statuses: {e}")


async def add_camera(name=None, branch_id=None, activate=False):
    if branch_id is None:
        print("branch_id is required")
        return None

    try:
        camera_id = _generate_camera_id()
        secret = _generate_camera_secret()
        return await _fetchrow(
            """
            INSERT INTO cameras (camera_id, branch_id, name, secret, activate)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING camera_id, branch_id, name, secret, activate, created_at;
            """,
            camera_id,
            branch_id,
            name,
            secret,
            activate,
        )
    except Exception as e:
        print(f"Error adding camera: {e}")
        return None


async def update_camera(camera_id, name=None, branch_id=None, activate=None):
    try:
        return await _fetchrow(
            """
            UPDATE cameras
            SET branch_id = COALESCE($1, branch_id),
                name = COALESCE($2, name),
                activate = COALESCE($3, activate)
            WHERE camera_id = $4
            RETURNING camera_id, branch_id, name, secret, activate, created_at;
            """,
            branch_id,
            name,
            activate,
            camera_id,
        )
    except Exception as e:
        print(f"Error updating camera: {e}")
        return None


async def reset_camera_secret(camera_id):
    try:
        new_secret = _generate_camera_secret()
        return await _fetchrow(
            """
            UPDATE cameras
            SET secret = $1
            WHERE camera_id = $2
            RETURNING camera_id, branch_id, name, secret, active, created_at;
            """,
            new_secret,
            camera_id,
        )
    except Exception as e:
        print(f"Error resetting camera secret: {e}")
        return None


async def delete_camera(camera_id):
    try:
        row = await _fetchrow(
            """
            DELETE FROM cameras
            WHERE camera_id = $1
            RETURNING camera_id;
            """,
            camera_id,
        )
        return row is not None
    except Exception as e:
        print(f"Error deleting camera: {e}")
        return False

async def create_branch(group_id, name, thresholds=None, model_id=None):
    try:
        final_thresholds = thresholds if thresholds is not None else {"activate": False, "sensors": {}}
        return await _fetchrow(
            """
            INSERT INTO branches (group_id, name, thresholds, model_id)
            VALUES ($1, $2, $3::jsonb, $4)
            RETURNING branch_id, group_id, name, thresholds, model_id, created_at;
            """,
            group_id,
            name,
            json.dumps(final_thresholds),
            uuid.UUID(model_id) if isinstance(model_id, str) and model_id else model_id,
        )
    except Exception as e:
        print(f"Error creating branch: {e}")
        return None


async def get_branches(group_id=None):
    try:
        if group_id is not None:
            return await _fetch(
                """
                SELECT branch_id, group_id, name, thresholds, model_id, created_at
                FROM branches
                WHERE group_id = $1
                ORDER BY branch_id DESC;
                """,
                group_id,
            )

        return await _fetch(
            """
            SELECT branch_id, group_id, name, thresholds, model_id, created_at FROM branches;
            """
        )
    except Exception as e:
        print(f"Error getting branches: {e}")
        return []


async def get_branch(branch_id, group_id=None):
    try:
        if group_id is not None:
            return await _fetchrow(
                """
                SELECT branch_id, group_id, name, thresholds, model_id, created_at
                FROM branches
                WHERE branch_id = $1 AND group_id = $2;
                """,
                branch_id,
                group_id,
            )

        return await _fetchrow(
            """
            SELECT branch_id, group_id, name, thresholds, model_id, created_at
            FROM branches
            WHERE branch_id = $1;
            """,
            branch_id,
        )
    except Exception as e:
        print(f"Error getting branch: {e}")
        return None


async def update_branch(branch_id, group_id, name, thresholds=None, model_id=None):
    try:
        return await _fetchrow(
            """
            UPDATE branches
            SET group_id = $1, name = $2, thresholds = $3::jsonb, model_id = $4
            WHERE branch_id = $5
            RETURNING branch_id, group_id, name, thresholds, model_id, created_at;
            """,
            group_id,
            name,
            json.dumps(thresholds) if thresholds else None,
            uuid.UUID(model_id) if isinstance(model_id, str) and model_id else model_id,
            branch_id,
        )
    except Exception as e:
        print(f"Error updating branch: {e}")
        return None


async def delete_branch(branch_id):
    try:
        row = await _fetchrow(
            """
            DELETE FROM branches
            WHERE branch_id = $1
            RETURNING branch_id;
            """,
            branch_id,
        )
        return row is not None
    except Exception as e:
        print(f"Error deleting branch: {e}")
        return False


async def create_group(name):
    try:
        return await _fetchrow(
            """
            INSERT INTO groups (name)
            VALUES ($1)
            RETURNING group_id, name, created_at;
            """,
            name,
        )
    except Exception as e:
        print(f"Error creating group: {e}")
        return None


async def get_groups():
    try:
        return await _fetch(
            """
            SELECT group_id, name, created_at
            FROM groups
            ORDER BY group_id DESC;
            """
        )
    except Exception as e:
        print(f"Error getting groups: {e}")
        return []


async def get_group(group_id):
    try:
        return await _fetchrow(
            """
            SELECT group_id, name, created_at
            FROM groups
            WHERE group_id = $1;
            """,
            group_id,
        )
    except Exception as e:
        print(f"Error getting group: {e}")
        return None


async def update_group(group_id, name):
    try:
        return await _fetchrow(
            """
            UPDATE groups
            SET name = $1
            WHERE group_id = $2
            RETURNING group_id, name, created_at;
            """,
            name,
            group_id,
        )
    except Exception as e:
        print(f"Error updating group: {e}")
        return None

async def get_sensor_to_branch_mapping():
    try:
        rows = await _fetch("SELECT sensor_id, branch_id FROM sensors WHERE deleted_at IS NULL;")
        return {row["sensor_id"]: row["branch_id"] for row in rows}
    except Exception as e:
        print(f"Error getting sensor to branch mapping: {e}")
        return {}

async def get_all_branch_thresholds():
    try:
        rows = await _fetch("SELECT branch_id, thresholds FROM branches;")
        return {row["branch_id"]: row["thresholds"] or {} for row in rows}
    except Exception as e:
        print(f"Error getting all branch thresholds: {e}")
        return {}

async def update_branch_thresholds(branch_id, thresholds):
    try:
        await _execute(
            "UPDATE branches SET thresholds = $1::jsonb WHERE branch_id = $2;",
            json.dumps(thresholds),
            branch_id,
        )
        return True
    except Exception as e:
        print(f"Error updating branch thresholds: {e}")
        return False


async def create_alert(branch_id, message, level):
    try:
        return await _fetchrow(
            """
            INSERT INTO alerts (branch_id, message, level)
            VALUES ($1, $2, $3)
            RETURNING alert_id, branch_id, message, level, is_read, created_at;
            """,
            branch_id,
            message,
            level,
        )
    except Exception as e:
        print(f"Error creating alert: {e}")
        return None


async def get_alerts_by_branch(branch_id, limit=None, unread_only=False):
    try:
        query = """
            SELECT alert_id, branch_id, message, level, is_read, created_at
            FROM alerts
            WHERE branch_id = $1
        """
        if unread_only:
            query += " AND is_read = FALSE"
            
        query += " ORDER BY created_at DESC"
        
        if limit is not None:
            query += f" LIMIT {int(limit)}"
        
        return await _fetch(query + ";", branch_id)
    except Exception as e:
        print(f"Error getting alerts by branch: {e}")
        return []


async def mark_alert_as_read_db(alert_id):
    try:
        return await _fetchrow(
            """
            UPDATE alerts
            SET is_read = TRUE
            WHERE alert_id = $1
            RETURNING alert_id, is_read;
            """,
            alert_id,
        )
    except Exception as e:
        print(f"Error marking alert as read: {e}")
        return None

async def delete_group(group_id):
    try:
        row = await _fetchrow(
            """
            DELETE FROM groups
            WHERE group_id = $1
            RETURNING group_id;
            """,
            group_id,
        )
        return row is not None
    except Exception as e:
        print(f"Error deleting group: {e}")
        return False


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


async def create_user(username, password, group_id=None, role="user"):
    try:
        return await _fetchrow(
            """
            INSERT INTO users (username, password_hash, group_id, role)
            VALUES ($1, $2, $3, $4)
            RETURNING user_id, group_id, username, role, created_at;
            """,
            username,
            _hash_password(password),
            group_id,
            role,
        )
    except Exception as e:
        print(f"Error creating user: {e}")
        return None


async def ensure_default_admin_user():
    try:
        # 1. Ensure Superadmin
        superadmin_username = config.SUPERADMIN_USERNAME
        existing_superadmin = await get_user_by_username(superadmin_username)

        if existing_superadmin is None:
            existing_superadmin = await create_user(
                username=superadmin_username,
                password=config.SUPERADMIN_PASSWORD,
                role="superadmin",
            )
            if existing_superadmin:
                print(f"[STARTUP] Created default superadmin: {superadmin_username}")
        else:
            if existing_superadmin.get("role") != "superadmin":
                await _execute(
                    "UPDATE users SET role = 'superadmin' WHERE user_id = $1",
                    existing_superadmin["user_id"]
                )
                existing_superadmin["role"] = "superadmin"
            print(f"[STARTUP] Superadmin '{superadmin_username}' is ready")

        # 2. Ensure Default Admin
        existing_admin = await get_user_by_username("admin")
        if existing_admin is None:
            await create_user(
                username="admin",
                password="admin123",
                role="admin",
            )
            print("[STARTUP] Created default admin: admin")
        elif existing_admin.get("role") != "admin":
            await _execute(
                "UPDATE users SET role = 'admin' WHERE user_id = $1",
                existing_admin["user_id"]
            )
            print("[STARTUP] Fixed role for user 'admin' to 'admin'")

        return existing_superadmin

        return await _fetchrow(
            """
            SELECT user_id, group_id, username, role, created_at
            FROM users
            WHERE role = 'superadmin'
            ORDER BY user_id ASC
            LIMIT 1;
            """
        )
    except Exception as e:
        print(f"Error ensuring default admin user: {e}")
        return None


async def get_users(group_id=None):
    try:
        if group_id is not None:
            return await _fetch(
                """
                SELECT user_id, group_id, username, role, created_at
                FROM users
                WHERE group_id = $1
                ORDER BY user_id DESC;
                """,
                group_id,
            )

        return await _fetch(
            """
            SELECT user_id, group_id, username, role, created_at
            FROM users
            ORDER BY user_id DESC;
            """
        )
    except Exception as e:
        print(f"Error getting users: {e}")
        return []


async def get_user(user_id):
    try:
        return await _fetchrow(
            """
            SELECT user_id, group_id, username, role, created_at
            FROM users
            WHERE user_id = $1;
            """,
            user_id,
        )
    except Exception as e:
        print(f"Error getting user: {e}")
        return None


async def get_user_by_username(username):
    try:
        return await _fetchrow(
            """
            SELECT user_id, group_id, username, role, created_at
            FROM users
            WHERE username = $1;
            """,
            username,
        )
    except Exception as e:
        print(f"Error getting user by username: {e}")
        return None


async def authenticate_user(username, password):
    try:
        return await _fetchrow(
            """
            SELECT user_id, group_id, username, role, created_at
            FROM users
            WHERE username = $1 AND password_hash = $2;
            """,
            username,
            _hash_password(password),
        )
    except Exception as e:
        print(f"Error authenticating user: {e}")
        return None


async def update_user(user_id, username, group_id=None, role="user", password=None):
    try:
        if password:
            return await _fetchrow(
                """
                UPDATE users
                SET username = $1, group_id = $2, role = $3, password_hash = $4
                WHERE user_id = $5
                RETURNING user_id, group_id, username, role, created_at;
                """,
                username,
                group_id,
                role,
                _hash_password(password),
                user_id,
            )
        else:
            return await _fetchrow(
                """
                UPDATE users
                SET username = $1, group_id = $2, role = $3
                WHERE user_id = $4
                RETURNING user_id, group_id, username, role, created_at;
                """,
                username,
                group_id,
                role,
                user_id,
            )
    except Exception as e:
        print(f"Error updating user: {e}")
        return None


async def delete_user(user_id):
    try:
        row = await _fetchrow(
            """
            DELETE FROM users
            WHERE user_id = $1
            RETURNING user_id;
            """,
            user_id,
        )
        return row is not None
    except Exception as e:
        print(f"Error deleting user: {e}")
        return False


# --- Job Management ---

async def create_job_db(job_id, branch_id, user_id, secret, dataset_params, feature_params, forecast_params, model_params, status='pending', message=None):
    try:
        return await _fetchrow(
            """
            INSERT INTO jobs (
                job_id, branch_id, user_id, secret, 
                dataset_params, feature_engineering_params, 
                forecast_params, model_hyperparams, status, message
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            RETURNING job_id, secret, status, message, created_at;
            """,
            job_id,
            branch_id,
            user_id,
            secret,
            json.dumps(dataset_params),
            json.dumps(feature_params),
            json.dumps(forecast_params),
            json.dumps(model_params),
            status,
            message,
        )
    except Exception as e:
        print(f"Error creating job in DB: {e}")
        return None


async def get_job_db(job_id):
    try:
        return await _fetchrow(
            """
            SELECT j.*, m.name as model_name 
            FROM jobs j
            LEFT JOIN models m ON m.model_id = j.model_id
            WHERE j.job_id = $1;
            """,
            job_id,
        )
    except Exception as e:
        print(f"Error getting job from DB: {e}")
        return None


async def get_jobs_db(group_id=None, status=None, limit=100):
    try:
        query = """
            SELECT j.*, m.name as model_name
            FROM jobs j
            JOIN branches b ON b.branch_id = j.branch_id
            LEFT JOIN models m ON m.model_id = j.model_id
            WHERE 1=1
        """
        params = []
        param_index = 1

        if group_id is not None:
            query += f" AND b.group_id = ${param_index}"
            params.append(group_id)
            param_index += 1

        if status is not None:
            query += f" AND j.status = ${param_index}"
            params.append(status)
            param_index += 1

        query += f" ORDER BY j.created_at DESC LIMIT ${param_index}"
        params.append(limit)

        return await _fetch(query, *params)
    except Exception as e:
        print(f"Error getting jobs from DB: {e}")
        return []


async def update_job_status_db(job_id, status, result=None, message=None, model_id=None):
    try:
        if result is not None:
            return await _fetchrow(
                """
                UPDATE jobs 
                SET status = $1, result = $2, message = COALESCE($3, message), model_id = COALESCE($4, model_id), updated_at = NOW()
                WHERE job_id = $5
                RETURNING job_id, status, message, model_id, updated_at;
                """,
                status,
                json.dumps(result),
                message,
                uuid.UUID(model_id) if model_id else None,
                job_id,
            )
        else:
            return await _fetchrow(
                """
                UPDATE jobs 
                SET status = $1, message = COALESCE($2, message), model_id = COALESCE($3, model_id), updated_at = NOW()
                WHERE job_id = $4
                RETURNING job_id, status, message, model_id, updated_at;
                """,
                status,
                message,
                uuid.UUID(model_id) if model_id else None,
                job_id,
            )
    except Exception as e:
        print(f"Error updating job status: {e}")
        return None


async def verify_job_data_exists(branch_id: int, features: list, start_time: datetime, end_time: datetime):
    try:
        missing_features = []
        
        sensor_features = [f for f in features if f != "people"]
        for feat in sensor_features:
            count = await _fetchrow(
                """
                SELECT COUNT(*) as count
                FROM values v
                JOIN sensors s ON s.sensor_id = v.sensor_id
                WHERE s.branch_id = $1 AND v.created_at BETWEEN $2 AND $3
                  AND (v.value #>> '{}')::jsonb ? $4;
                """,
                branch_id, start_time, end_time, feat
            )
            if not count or count["count"] == 0:
                missing_features.append(feat)

        if "people" in features:
            count = await _fetchrow(
                """
                SELECT COUNT(*) as count
                FROM image_analysis ia
                JOIN cameras c ON c.camera_id = ia.camera_id
                WHERE c.branch_id = $1 AND ia.created_at BETWEEN $2 AND $3;
                """,
                branch_id, start_time, end_time
            )
            if not count or count["count"] == 0:
                missing_features.append("people")

        if missing_features:
            return False, f"Insufficient data for features: {', '.join(missing_features)}"
        
        return True, ""
    except Exception as e:
        print(f"Error verifying job data: {e}")
        return False, f"System error during data verification: {str(e)}"


async def cancel_job_db(job_id):
    try:
        return await _fetchrow(
            """
            UPDATE jobs 
            SET status = 'cancelled', updated_at = NOW()
            WHERE job_id = $1
            RETURNING job_id, status;
            """,
            job_id,
        )
    except Exception as e:
        print(f"Error cancelling job in DB: {e}")
        return None


async def save_image_analysis(image_id, camera_id, image_path, people_count, metadata=None):
    try:
        return await _fetchrow(
            """
            INSERT INTO image_analysis (image_id, camera_id, image_path, people_count, metadata)
            VALUES ($1, $2, $3, $4, $5::jsonb)
            RETURNING image_id, camera_id, image_path, people_count, metadata, created_at, updated_at;
            """,
            image_id,
            camera_id,
            image_path,
            people_count,
            json.dumps(metadata) if metadata else None,
        )
    except Exception as e:
        print(f"Error saving image analysis: {e}")
        return None


async def get_image_analysis(image_id):
    try:
        return await _fetchrow(
            """
            SELECT image_id, camera_id, image_path, people_count, metadata, created_at, updated_at
            FROM image_analysis
            WHERE image_id = $1;
            """,
            image_id,
        )
    except Exception as e:
        print(f"Error getting image analysis: {e}")
        return None


async def get_image_analysis_by_camera_last_10_minutes(camera_id):
    """Get image analysis from the last 10 minutes for a camera."""
    try:
        return await _fetch(
            """
            SELECT image_id, camera_id, image_path, people_count, metadata, created_at, updated_at
            FROM image_analysis
            WHERE camera_id = $1
              AND created_at >= NOW() - INTERVAL '11 minutes'
              AND created_at <= NOW()
            ORDER BY created_at DESC;
            """,
            camera_id,
        )
    except Exception as e:
        print(f"Error getting image analysis from last 10 minutes: {e}")
        return []


async def create_user_session(
    session_id,
    user_id,
    expires_at,
    ip_address=None,
    user_agent=None,
):
    try:
        return await _fetchrow(
            """
            INSERT INTO user_sessions (session_id, user_id, ip_address, user_agent, expires_at)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING session_id, user_id, ip_address, user_agent, is_active, expires_at, created_at, updated_at, last_seen_at;
            """,
            session_id,
            user_id,
            ip_address,
            user_agent,
            expires_at,
        )
    except Exception as e:
        print(f"Error creating user session: {e}")
        return None


async def get_user_session(session_id):
    try:
        return await _fetchrow(
            """
            SELECT session_id, user_id, ip_address, user_agent, is_active, expires_at, created_at, updated_at, last_seen_at
            FROM user_sessions
            WHERE session_id = $1;
            """,
            session_id,
        )
    except Exception as e:
        print(f"Error getting user session: {e}")
        return None


async def get_active_user_session(session_id):
    try:
        return await _fetchrow(
            """
            SELECT session_id, user_id, ip_address, user_agent, is_active, expires_at, created_at, updated_at, last_seen_at
            FROM user_sessions
            WHERE session_id = $1
              AND is_active = TRUE
              AND expires_at > NOW();
            """,
            session_id,
        )
    except Exception as e:
        print(f"Error getting active user session: {e}")
        return None


async def touch_user_session(session_id):
    try:
        return await _fetchrow(
            """
            UPDATE user_sessions
            SET last_seen_at = NOW(), updated_at = NOW()
            WHERE session_id = $1
              AND is_active = TRUE
              AND expires_at > NOW()
            RETURNING session_id, user_id, ip_address, user_agent, is_active, expires_at, created_at, updated_at, last_seen_at;
            """,
            session_id,
        )
    except Exception as e:
        print(f"Error touching user session: {e}")
        return None


async def revoke_user_session(session_id):
    try:
        row = await _fetchrow(
            """
            UPDATE user_sessions
            SET is_active = FALSE, updated_at = NOW()
            WHERE session_id = $1
            RETURNING session_id;
            """,
            session_id,
        )
        return row is not None
    except Exception as e:
        print(f"Error revoking user session: {e}")
        return False


async def revoke_all_user_sessions(user_id):
    try:
        status = await _execute(
            """
            UPDATE user_sessions
            SET is_active = FALSE, updated_at = NOW()
            WHERE user_id = $1 AND is_active = TRUE;
            """,
            user_id,
        )
        return isinstance(status, str)
    except Exception as e:
        print(f"Error revoking all user sessions: {e}")
        return False


async def get_user_sessions(user_id, active_only=False):
    try:
        if active_only:
            return await _fetch(
                """
                SELECT session_id, user_id, ip_address, user_agent, is_active, expires_at, created_at, updated_at, last_seen_at
                FROM user_sessions
                WHERE user_id = $1
                  AND is_active = TRUE
                  AND expires_at > NOW()
                ORDER BY created_at DESC;
                """,
                user_id,
            )

        return await _fetch(
            """
            SELECT session_id, user_id, ip_address, user_agent, is_active, expires_at, created_at, updated_at, last_seen_at
            FROM user_sessions
            WHERE user_id = $1
            ORDER BY created_at DESC;
            """,
            user_id,
        )
    except Exception as e:
        print(f"Error getting user sessions: {e}")
        return []


async def delete_expired_user_sessions():
    try:
        status = await _execute(
            """
            DELETE FROM user_sessions
            WHERE expires_at <= NOW() OR is_active = FALSE;
            """
        )
        return isinstance(status, str)
    except Exception as e:
        print(f"Error deleting expired user sessions: {e}")
        return False


async def delete_model_db(model_id: str, group_id: int):
    try:
        return await _fetchrow(
            "UPDATE models SET deleted_at = NOW() WHERE model_id = $1 AND group_id = $2 AND deleted_at IS NULL RETURNING model_id, group_id, name, created_at, deleted_at;",
            uuid.UUID(model_id) if isinstance(model_id, str) else model_id,
            group_id
        )
    except Exception as e:
        print(f"Error deleting model: {e}")
        return None


async def get_or_create_model(group_id: int, model_id: str, name: str):
    try:
        row = await _fetchrow(
            """
            INSERT INTO models (model_id, group_id, name)
            VALUES ($1, $2, $3)
            ON CONFLICT (model_id) DO UPDATE SET name = EXCLUDED.name
            RETURNING model_id, group_id, name, created_at;
            """,
            uuid.UUID(model_id) if isinstance(model_id, str) else model_id,
            group_id,
            name,
        )
        return row
    except Exception as e:
        print(f"Error in get_or_create_model: {e}")
        return None


async def get_models_db(group_id: int):
    try:
        return await _fetch(
            """
            SELECT model_id, group_id, name, created_at, deleted_at
            FROM models 
            WHERE group_id = $1 AND deleted_at IS NULL
            ORDER BY created_at DESC;
            """, 
            group_id
        )
    except Exception as e:
        print(f"Error getting models: {e}")
        return []


async def update_model_name_db(model_id: str, name: str, group_id: int):
    try:
        return await _fetchrow(
            "UPDATE models SET name = $1 WHERE model_id = $2 AND group_id = $3 AND deleted_at IS NULL RETURNING model_id, group_id, name, created_at, deleted_at;",
            name,
            uuid.UUID(model_id) if isinstance(model_id, str) else model_id,
            group_id
        )
    except Exception as e:
        print(f"Error updating model name: {e}")
        return None