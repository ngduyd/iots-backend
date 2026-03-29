import hashlib

from app.db.session import fetch, fetchrow, execute

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

async def create_user(username, password, group_id=None, role="user"):
    return await fetchrow(
        """
        INSERT INTO users (username, password_hash, group_id, role)
        VALUES ($1, $2, $3, $4)
        RETURNING user_id, group_id, username, role, created_at;
        """,
        username,
        hash_password(password),
        group_id,
        role,
    )

async def get_users(group_id=None):
    if group_id is not None:
        return await fetch(
            """
            SELECT user_id, group_id, username, role, created_at
            FROM users
            WHERE group_id = $1
            ORDER BY user_id DESC;
            """,
            group_id,
        )
    return await fetch(
        """
        SELECT user_id, group_id, username, role, created_at
        FROM users
        ORDER BY user_id DESC;
        """
    )

async def get_user(user_id):
    return await fetchrow(
        """
        SELECT user_id, group_id, username, role, created_at
        FROM users
        WHERE user_id = $1;
        """,
        user_id,
    )

async def get_user_by_username(username):
    return await fetchrow(
        """
        SELECT user_id, group_id, username, role, created_at
        FROM users
        WHERE username = $1;
        """,
        username,
    )

async def authenticate_user(username, password):
    return await fetchrow(
        """
        SELECT user_id, group_id, username, role, created_at
        FROM users
        WHERE username = $1 AND password_hash = $2;
        """,
        username,
        hash_password(password),
    )

async def update_user(user_id, username, group_id=None, role="user", password=None):
    if password:
        return await fetchrow(
            """
            UPDATE users
            SET username = $1, group_id = $2, role = $3, password_hash = $4
            WHERE user_id = $5
            RETURNING user_id, group_id, username, role, created_at;
            """,
            username,
            group_id,
            role,
            hash_password(password),
            user_id,
        )
    else:
        return await fetchrow(
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

async def delete_user(user_id):
    row = await fetchrow(
        """
        DELETE FROM users
        WHERE user_id = $1
        RETURNING user_id;
        """,
        user_id,
    )
    return row is not None

async def ensure_default_admin_user():
    existing_superadmin = await get_user_by_username("superadmin")
    if existing_superadmin is not None and existing_superadmin.get("role") != "superadmin":
        existing_superadmin = await fetchrow(
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
        existing_admin = await fetchrow(
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

    return await fetchrow(
        """
        SELECT user_id, group_id, username, role, created_at
        FROM users
        WHERE role = 'superadmin'
        ORDER BY user_id ASC
        LIMIT 1;
        """
    )

async def create_user_session(session_id, user_id, expires_at, ip_address=None, user_agent=None):
    return await fetchrow(
        """
        INSERT INTO user_sessions (session_id, user_id, ip_address, user_agent, expires_at)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING session_id, user_id, ip_address, user_agent, is_active, expires_at, created_at, updated_at, last_seen_at;
        """,
        session_id, user_id, ip_address, user_agent, expires_at,
    )

async def get_user_session(session_id):
    return await fetchrow(
        "SELECT session_id, user_id, ip_address, user_agent, is_active, expires_at, created_at, updated_at, last_seen_at FROM user_sessions WHERE session_id = $1;",
        session_id,
    )

async def get_active_user_session(session_id):
    return await fetchrow(
        """
        SELECT session_id, user_id, ip_address, user_agent, is_active, expires_at, created_at, updated_at, last_seen_at
        FROM user_sessions
        WHERE session_id = $1 AND is_active = TRUE AND expires_at > NOW();
        """,
        session_id,
    )

async def touch_user_session(session_id):
    return await fetchrow(
        """
        UPDATE user_sessions
        SET last_seen_at = NOW(), updated_at = NOW()
        WHERE session_id = $1 AND is_active = TRUE AND expires_at > NOW()
        RETURNING session_id, user_id, ip_address, user_agent, is_active, expires_at, created_at, updated_at, last_seen_at;
        """,
        session_id,
    )

async def revoke_user_session(session_id):
    row = await fetchrow(
        "UPDATE user_sessions SET is_active = FALSE, updated_at = NOW() WHERE session_id = $1 RETURNING session_id;",
        session_id,
    )
    return row is not None

async def revoke_all_user_sessions(user_id):
    await execute("UPDATE user_sessions SET is_active = FALSE, updated_at = NOW() WHERE user_id = $1 AND is_active = TRUE;", user_id)
    return True

async def get_user_sessions(user_id, active_only=False):
    if active_only:
        return await fetch(
            """
            SELECT session_id, user_id, ip_address, user_agent, is_active, expires_at, created_at, updated_at, last_seen_at
            FROM user_sessions
            WHERE user_id = $1 AND is_active = TRUE AND expires_at > NOW()
            ORDER BY created_at DESC;
            """,
            user_id,
        )
    return await fetch(
        "SELECT session_id, user_id, ip_address, user_agent, is_active, expires_at, created_at, updated_at, last_seen_at FROM user_sessions WHERE user_id = $1 ORDER BY created_at DESC;",
        user_id,
    )

async def delete_expired_user_sessions():
    await execute("DELETE FROM user_sessions WHERE expires_at <= NOW() OR is_active = FALSE;")
    return True
