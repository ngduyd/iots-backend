import asyncio
from datetime import datetime
import hashlib
import json
import os
import time

import asyncpg

from app.core import config

db_pool = None
_pool_lock = asyncio.Lock()


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
                        alert VARCHAR(100) DEFAULT 'none',
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
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
                        active BOOLEAN NOT NULL DEFAULT FALSE,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    """
                )
                await connection.execute(
                    """
                    ALTER TABLE cameras
                    ADD COLUMN IF NOT EXISTS active BOOLEAN NOT NULL DEFAULT FALSE;
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
                    CREATE TRIGGER trg_sync_sensor_status_from_value
                    AFTER INSERT ON values
                    FOR EACH ROW
                    EXECUTE FUNCTION sync_sensor_status_from_value();
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
    """Return the single camera for a branch (branches have at most 1 camera)."""
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
                SELECT c.camera_id, c.branch_id, c.name, c.secret, c.active, c.created_at, c.status
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
            SELECT camera_id, branch_id, name, secret, active, created_at, status
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
            SELECT camera_id, branch_id, name, secret, active, created_at, status
            FROM cameras
            WHERE active = TRUE
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
                SELECT c.camera_id, c.branch_id, c.name, c.secret, c.active, c.created_at, c.status
                FROM cameras c
                JOIN branches b ON b.branch_id = c.branch_id
                WHERE c.camera_id = $1 AND b.group_id = $2;
                """,
                camera_id,
                group_id,
            )

        return await _fetchrow(
            """
            SELECT camera_id, branch_id, name, secret, active, created_at, status
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


async def add_camera(name=None, branch_id=None, active=False):
    if branch_id is None:
        print("branch_id is required")
        return None

    try:
        camera_id = _generate_camera_id()
        secret = _generate_camera_secret()
        return await _fetchrow(
            """
            INSERT INTO cameras (camera_id, branch_id, name, secret, active)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING camera_id, branch_id, name, secret, active, created_at;
            """,
            camera_id,
            branch_id,
            name,
            secret,
            active,
        )
    except Exception as e:
        print(f"Error adding camera: {e}")
        return None


async def update_camera(camera_id, name=None, branch_id=None, active=None):
    try:
        return await _fetchrow(
            """
            UPDATE cameras
            SET branch_id = COALESCE($1, branch_id),
                name = COALESCE($2, name),
                active = COALESCE($3, active)
            WHERE camera_id = $4
            RETURNING camera_id, branch_id, name, secret, active, created_at;
            """,
            branch_id,
            name,
            active,
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

async def create_branch(group_id, name, alert="none"):
    try:
        return await _fetchrow(
            """
            INSERT INTO branches (group_id, name, alert)
            VALUES ($1, $2, $3)
            RETURNING branch_id, group_id, name, alert, created_at;
            """,
            group_id,
            name,
            alert,
        )
    except Exception as e:
        print(f"Error creating branch: {e}")
        return None


async def get_branches(group_id=None):
    try:
        if group_id is not None:
            return await _fetch(
                """
                SELECT branch_id, group_id, name, alert, created_at
                FROM branches
                WHERE group_id = $1
                ORDER BY branch_id DESC;
                """,
                group_id,
            )

        return await _fetch(
            """
            SELECT * FROM branches;
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
                SELECT branch_id, group_id, name, alert, created_at
                FROM branches
                WHERE branch_id = $1 AND group_id = $2;
                """,
                branch_id,
                group_id,
            )

        return await _fetchrow(
            """
            SELECT branch_id, group_id, name, alert, created_at
            FROM branches
            WHERE branch_id = $1;
            """,
            branch_id,
        )
    except Exception as e:
        print(f"Error getting branch: {e}")
        return None


async def update_branch(branch_id, group_id, name, alert="none"):
    try:
        return await _fetchrow(
            """
            UPDATE branches
            SET group_id = $1, name = $2, alert = $3
            WHERE branch_id = $4
            RETURNING branch_id, group_id, name, alert, created_at;
            """,
            group_id,
            name,
            alert,
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
        existing_superadmin = await get_user_by_username("superadmin")
        if existing_superadmin is not None and existing_superadmin.get("role") != "superadmin":
            existing_superadmin = await _fetchrow(
                """
                UPDATE users
                SET role = 'superadmin'
                WHERE user_id = $1
                RETURNING user_id, group_id, username, role, created_at;
                """,
                existing_superadmin["user_id"],
            )

        if existing_superadmin is None:
            existing_superadmin = await create_user(
                username="superadmin",
                password="superadmin123",
                role="superadmin",
            )

        existing_admin = await get_user_by_username("admin")
        if existing_admin is None:
            existing_admin = await create_user(
                username="admin",
                password="admin123",
                role="admin",
            )
        elif existing_admin.get("role") != "admin":
            existing_admin = await _fetchrow(
                """
                UPDATE users
                SET role = 'admin'
                WHERE user_id = $1
                RETURNING user_id, group_id, username, role, created_at;
                """,
                existing_admin["user_id"],
            )

        if existing_superadmin is not None:
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


async def update_user(user_id, username, group_id=None, role="user"):
    try:
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