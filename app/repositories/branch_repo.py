import json

from app.db.session import fetch, fetchrow, execute

async def create_branch(group_id, name, thresholds=None):
    final_thresholds = thresholds if thresholds is not None else {"activate": False, "sensors": {}}
    return await fetchrow(
        "INSERT INTO branches (group_id, name, thresholds) VALUES ($1, $2, $3::jsonb) RETURNING branch_id, group_id, name, thresholds, created_at;",
        group_id, name, json.dumps(final_thresholds),
    )

async def get_branches(group_id=None):
    if group_id is not None:
        return await fetch(
            "SELECT branch_id, group_id, name, thresholds, created_at FROM branches WHERE group_id = $1 ORDER BY branch_id DESC;",
            group_id,
        )
    return await fetch("SELECT branch_id, group_id, name, thresholds, created_at FROM branches ORDER BY branch_id DESC;")

async def get_branch(branch_id, group_id=None):
    if group_id is not None:
        return await fetchrow(
            "SELECT branch_id, group_id, name, thresholds, created_at FROM branches WHERE branch_id = $1 AND group_id = $2;",
            branch_id, group_id,
        )
    return await fetchrow("SELECT branch_id, group_id, name, thresholds, created_at FROM branches WHERE branch_id = $1;", branch_id)

async def update_branch(branch_id, group_id, name, thresholds=None):
    return await fetchrow(
        "UPDATE branches SET group_id = $1, name = $2, thresholds = $3::jsonb WHERE branch_id = $4 RETURNING branch_id, group_id, name, thresholds, created_at;",
        group_id, name, json.dumps(thresholds) if thresholds else None, branch_id,
    )

async def delete_branch(branch_id):
    row = await fetchrow("DELETE FROM branches WHERE branch_id = $1 RETURNING branch_id;", branch_id)
    return row is not None

async def create_group(name):
    return await fetchrow("INSERT INTO groups (name) VALUES ($1) RETURNING group_id, name, created_at;", name)

async def get_groups():
    return await fetch("SELECT group_id, name, created_at FROM groups ORDER BY group_id DESC;")

async def get_group(group_id):
    return await fetchrow("SELECT group_id, name, created_at FROM groups WHERE group_id = $1;", group_id)

async def update_group(group_id, name):
    return await fetchrow("UPDATE groups SET name = $1 WHERE group_id = $2 RETURNING group_id, name, created_at;", name, group_id)

async def delete_group(group_id):
    row = await fetchrow("DELETE FROM groups WHERE group_id = $1 RETURNING group_id;", group_id)
    return row is not None

async def get_all_branch_thresholds():
    rows = await fetch("SELECT branch_id, thresholds FROM branches;")
    return {row["branch_id"]: row["thresholds"] or {} for row in rows}

async def update_branch_thresholds(branch_id, thresholds):
    await execute("UPDATE branches SET thresholds = $1::jsonb WHERE branch_id = $2;", json.dumps(thresholds), branch_id)
    return True

async def get_branch_data_for_export(branch_id: int, from_time, to_time):
    sensor_values = await fetch(
        """
        SELECT v.sensor_id, s.name as sensor_name, v.value, v.created_at
        FROM values v JOIN sensors s ON s.sensor_id = v.sensor_id
        WHERE s.branch_id = $1 AND s.deleted_at IS NULL AND v.created_at >= $2 AND v.created_at <= $3
        ORDER BY v.created_at ASC;
        """,
        branch_id, from_time, to_time,
    )
    people_counts = await fetch(
        """
        SELECT ia.people_count, ia.created_at
        FROM image_analysis ia JOIN cameras c ON c.camera_id = ia.camera_id
        WHERE c.branch_id = $1 AND ia.created_at >= $2 AND ia.created_at <= $3
        ORDER BY ia.created_at ASC;
        """,
        branch_id, from_time, to_time,
    )
    return sensor_values, people_counts
