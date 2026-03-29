import json
import os
import time
from datetime import datetime

from app.db.session import fetch, fetchrow, execute, get_db_pool

def generate_sensor_id():
    ts = int(time.time()).to_bytes(4, "big")
    rand = os.urandom(12)
    return (ts + rand).hex()

async def save_message(topic, payload, received_at=None):
    try:
        data = json.loads(payload)
        if received_at is not None:
            await execute(
                "INSERT INTO values (sensor_id, value, created_at) VALUES ($1, $2::jsonb, $3);",
                topic, json.dumps(data), received_at,
            )
        else:
            await execute(
                "INSERT INTO values (sensor_id, value) VALUES ($1, $2::jsonb);",
                topic, json.dumps(data),
            )
    except Exception as e:
        print(f"Error saving message: {e}")

async def save_messages_batch(items):
    if not items:
        return
    pool = await get_db_pool()
    if pool is None:
        return
    values = []
    for sensor_id, payload, received_at in items:
        if not sensor_id: continue
        try:
            parsed = json.loads(payload)
            values.append((sensor_id, json.dumps(parsed), received_at))
        except: continue
    if not values: return
    try:
        async with pool.acquire() as connection:
            await connection.executemany(
                "INSERT INTO values (sensor_id, value, created_at) VALUES ($1, $2::jsonb, $3);",
                values,
            )
    except Exception as e:
        print(f"Error saving message batch: {e}")

async def update_sensor_status(sensor_id, status):
    await execute(
        "UPDATE sensors SET status = $1, updated_at = NOW() WHERE sensor_id = $2 AND deleted_at IS NULL;",
        status, sensor_id
    )

async def get_all_sensor_status() -> dict:
    rows = await fetch("SELECT sensor_id, status FROM sensors WHERE deleted_at IS NULL;")
    return {row["sensor_id"]: row["status"] for row in rows}

async def get_sensors(limit=100, group_id=None):
    if group_id is not None:
        return await fetch(
            """
            SELECT s.sensor_id, s.name, s.status, s.updated_at
            FROM sensors s
            JOIN branches b ON b.branch_id = s.branch_id
            WHERE b.group_id = $1 AND s.deleted_at IS NULL
            ORDER BY s.updated_at DESC LIMIT $2;
            """,
            group_id, limit,
        )
    return await fetch(
        "SELECT sensor_id, name, status, updated_at FROM sensors WHERE deleted_at IS NULL ORDER BY updated_at DESC LIMIT $1;",
        limit
    )

async def get_sensor(sensor_id, group_id=None):
    if group_id is not None:
        return await fetchrow(
            """
            SELECT s.sensor_id, s.name, s.branch_id, s.status, s.updated_at
            FROM sensors s
            JOIN branches b ON b.branch_id = s.branch_id
            WHERE s.sensor_id = $1 AND b.group_id = $2 AND s.deleted_at IS NULL;
            """,
            sensor_id, group_id,
        )
    return await fetchrow(
        "SELECT sensor_id, name, branch_id, status, updated_at FROM sensors WHERE sensor_id = $1 AND deleted_at IS NULL;",
        sensor_id
    )

async def get_sensors_by_branch(branch_id, limit=100):
    return await fetch(
        "SELECT sensor_id, name, status, updated_at FROM sensors WHERE branch_id = $1 AND deleted_at IS NULL ORDER BY updated_at DESC LIMIT $2;",
        branch_id, limit
    )

async def get_sensor_values(sensor_id, limit=1000000, group_id=None, from_time: datetime | None = None, to_time: datetime | None = None):
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
            WHERE {' AND '.join(val_where)} AND s.deleted_at IS NULL AND b.group_id = ${group_idx}
            ORDER BY v.created_at DESC LIMIT ${limit_idx};
        """
    else:
        query = f"""
            SELECT v.sensor_id, v.value, v.created_at
            FROM values v
            JOIN sensors s ON s.sensor_id = v.sensor_id
            WHERE {' AND '.join(val_where)} AND s.deleted_at IS NULL
            ORDER BY v.created_at DESC LIMIT ${limit_idx};
        """
    return await fetch(query, *params)

async def add_sensor(sensor_name=None, branch_id=None):
    if branch_id is None: return None
    sensor_id = generate_sensor_id()
    return await fetchrow(
        "INSERT INTO sensors (sensor_id, name, branch_id) VALUES ($1, $2, $3) RETURNING sensor_id, name, status, updated_at;",
        sensor_id, sensor_name, branch_id,
    )

async def update_sensor(sensor_id, sensor_name=None, branch_id=None, delete=False):
    if delete:
        return await fetchrow(
            "UPDATE sensors SET deleted_at = NOW(), updated_at = NOW() WHERE sensor_id = $1 AND deleted_at IS NULL RETURNING sensor_id, name, status, updated_at;",
            sensor_id
        )
    return await fetchrow(
        "UPDATE sensors SET name = $1, branch_id = $2, updated_at = NOW() WHERE sensor_id = $3 AND deleted_at IS NULL RETURNING sensor_id, name, status, updated_at;",
        sensor_name, branch_id, sensor_id
    )

async def get_sensor_to_branch_mapping():
    rows = await fetch("SELECT sensor_id, branch_id FROM sensors WHERE deleted_at IS NULL;")
    return {row["sensor_id"]: row["branch_id"] for row in rows}

async def get_sensor_name(sensor_id):
    row = await fetchrow("SELECT name FROM sensors WHERE sensor_id = $1 AND deleted_at IS NULL;", sensor_id)
    return row["name"] if row else None
