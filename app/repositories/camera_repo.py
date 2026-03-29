import os

from app.db.session import fetch, fetchrow, execute

def generate_camera_id():
    import time
    ts = int(time.time()).to_bytes(4, "big")
    rand = os.urandom(12)
    return (ts + rand).hex()

def generate_camera_secret():
    return os.urandom(32).hex()

async def get_cameras(limit=100, group_id=None):
    if group_id is not None:
        return await fetch(
            """
            SELECT c.camera_id, c.branch_id, c.name, c.secret, c.activate, c.created_at, c.status
            FROM cameras c JOIN branches b ON b.branch_id = c.branch_id
            WHERE b.group_id = $1 ORDER BY c.camera_id DESC LIMIT $2;
            """,
            group_id, limit,
        )
    return await fetch(
        "SELECT camera_id, branch_id, name, secret, activate, created_at, status FROM cameras ORDER BY camera_id DESC LIMIT $1;",
        limit
    )

async def get_active_cameras():
    return await fetch("SELECT camera_id, branch_id, name, secret, activate, created_at, status FROM cameras WHERE activate = TRUE ORDER BY camera_id DESC;")

async def get_camera(camera_id, group_id=None):
    if group_id is not None:
        return await fetchrow(
            """
            SELECT c.camera_id, c.branch_id, c.name, c.secret, c.activate, c.created_at, c.status
            FROM cameras c JOIN branches b ON b.branch_id = c.branch_id
            WHERE c.camera_id = $1 AND b.group_id = $2;
            """,
            camera_id, group_id,
        )
    return await fetchrow("SELECT camera_id, branch_id, name, secret, activate, created_at, status FROM cameras WHERE camera_id = $1;", camera_id)

async def create_camera_access_request(camera_id, user_id, ttl_seconds=60):
    access_token = os.urandom(24).hex()
    return await fetchrow(
        """
        INSERT INTO camera_access_requests (camera_id, user_id, access_token, status, expires_at, updated_at)
        VALUES ($1, $2, $3, 'approved', NOW() + ($4 * INTERVAL '1 second'), NOW())
        RETURNING request_id, camera_id, user_id, access_token, status, expires_at, created_at;
        """,
        camera_id, user_id, access_token, ttl_seconds,
    )

async def verify_camera_access_request_by_token(access_token, ttl_seconds=60):
    return await fetchrow(
        """
        WITH candidate AS (
            SELECT request_id FROM camera_access_requests
            WHERE access_token = $1 AND status IN ('approved', 'used') AND expires_at > NOW()
            ORDER BY request_id DESC LIMIT 1
        )
        UPDATE camera_access_requests car
        SET status = 'used', expires_at = NOW() + ($2 * INTERVAL '1 second'), updated_at = NOW()
        FROM candidate WHERE car.request_id = candidate.request_id
        RETURNING car.request_id, car.camera_id, car.user_id, car.access_token, car.status, car.expires_at, car.created_at;
        """,
        access_token, ttl_seconds,
    )

async def verify_camera_stream(camera_id, secret):
    return await fetchrow(
        "UPDATE cameras SET status = 'online' WHERE camera_id = $1 AND secret = $2 RETURNING camera_id, branch_id, name;",
        camera_id, secret
    )

async def end_camera_stream(camera_id, secret):
    return await fetchrow(
        "UPDATE cameras SET status = 'offline' WHERE camera_id = $1 AND secret = $2 RETURNING camera_id, branch_id, name;",
        camera_id, secret
    )

async def reset_all_cameras_offline():
    await execute("UPDATE cameras SET status = 'offline';")

async def add_camera(name=None, branch_id=None, activate=False):
    if branch_id is None: return None
    camera_id = generate_camera_id()
    secret = generate_camera_secret()
    return await fetchrow(
        "INSERT INTO cameras (camera_id, branch_id, name, secret, activate) VALUES ($1, $2, $3, $4, $5) RETURNING camera_id, branch_id, name, secret, activate, created_at;",
        camera_id, branch_id, name, secret, activate,
    )

async def update_camera(camera_id, name=None, branch_id=None, activate=None):
    return await fetchrow(
        """
        UPDATE cameras
        SET branch_id = COALESCE($1, branch_id), name = COALESCE($2, name), activate = COALESCE($3, activate)
        WHERE camera_id = $4
        RETURNING camera_id, branch_id, name, secret, activate, created_at;
        """,
        branch_id, name, activate, camera_id,
    )

async def delete_camera(camera_id):
    row = await fetchrow("DELETE FROM cameras WHERE camera_id = $1 RETURNING camera_id;", camera_id)
    return row is not None

async def get_cameras_by_branch(branch_id, limit=100):
    return await fetch("SELECT camera_id, branch_id, name, secret, created_at, status FROM cameras WHERE branch_id = $1 ORDER BY created_at DESC LIMIT $2;", branch_id, limit)

async def get_camera_by_branch(branch_id):
    return await fetchrow("SELECT camera_id, branch_id, name, status, created_at FROM cameras WHERE branch_id = $1 LIMIT 1;", branch_id)

async def update_camera_status(camera_id, status):
    await execute("UPDATE cameras SET status = $1 WHERE camera_id = $2;", status, camera_id)

async def save_image_analysis(image_id, camera_id, image_path, people_count, metadata=None):
    import json
    return await fetchrow(
        """
        INSERT INTO image_analysis (image_id, camera_id, image_path, people_count, metadata)
        VALUES ($1, $2, $3, $4, $5::jsonb)
        RETURNING image_id, camera_id, image_path, people_count, metadata, created_at;
        """,
        image_id, camera_id, image_path, people_count, json.dumps(metadata) if metadata else None,
    )

async def get_latest_people_count_by_branch(branch_id: int):
    return await fetch(
        """
        SELECT ia.people_count, ia.created_at, ia.camera_id
        FROM image_analysis ia JOIN cameras c ON c.camera_id = ia.camera_id
        WHERE c.branch_id = $1 AND c.status = 'online' AND ia.created_at >= NOW() - INTERVAL '11 minutes'
        ORDER BY ia.created_at DESC;
        """,
        branch_id,
    )
