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
        rows = await connection.fetch(query, *args)
        return [dict(row) for row in rows]


async def _fetchrow(query, *args):
    pool = await get_db_pool()
    if pool is None:
        return None

    async with pool.acquire() as connection:
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
                        camera_id SERIAL PRIMARY KEY,
                        branch_id INT REFERENCES branches(branch_id),
                        name VARCHAR(50),
                        ip_address VARCHAR(50),
                        username VARCHAR(50),
                        password VARCHAR(50),
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    """
                )
                await connection.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_sensor_time ON values(sensor_id, created_at);
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


async def update_sensor_status(sensor_id, status):
    try:
        await _execute(
            "UPDATE sensors SET status = $1, updated_at = NOW() WHERE sensor_id = $2 AND deleted_at IS NULL;",
            status,
            sensor_id,
        )
    except Exception as e:
        print(f"Error updating sensor status: {e}")


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
                SELECT s.sensor_id, s.name, s.status, s.updated_at
                FROM sensors s
                JOIN branches b ON b.branch_id = s.branch_id
                WHERE s.sensor_id = $1 AND b.group_id = $2 AND s.deleted_at IS NULL;
                """,
                sensor_id,
                group_id,
            )

        return await _fetchrow(
            """
            SELECT sensor_id, name, status, updated_at
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


async def get_sensor_values(sensor_id, limit=100, group_id=None, from_time: datetime | None = None, to_time: datetime | None = None):
    try:
        where_clauses = ["s.sensor_id = $1", "s.deleted_at IS NULL"]
        params = [sensor_id]

        if group_id is not None:
            where_clauses.append(f"b.group_id = ${len(params) + 1}")
            params.append(group_id)

        if from_time is not None:
            where_clauses.append(f"v.created_at >= ${len(params) + 1}")
            params.append(from_time)

        if to_time is not None:
            where_clauses.append(f"v.created_at <= ${len(params) + 1}")
            params.append(to_time)

        limit_placeholder = f"${len(params) + 1}"
        params.append(limit)

        if group_id is not None:
            return await _fetch(
                f"""
                SELECT s.sensor_id, v.value, v.created_at
                FROM values v
                JOIN sensors s ON s.sensor_id = v.sensor_id
                JOIN branches b ON b.branch_id = s.branch_id
                WHERE {' AND '.join(where_clauses)}
                ORDER BY v.created_at DESC
                LIMIT {limit_placeholder};
                """,
                *params,
            )

        return await _fetch(
            f"""
            SELECT s.sensor_id, v.value, v.created_at
            FROM values v
            JOIN sensors s ON s.sensor_id = v.sensor_id
            WHERE {' AND '.join(where_clauses)}
            ORDER BY v.created_at DESC
            LIMIT {limit_placeholder};
            """,
            *params,
        )
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