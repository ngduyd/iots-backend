import json
import uuid

from app.db.session import fetch, fetchrow

async def create_job(job_id, branch_id, user_id, secret, dataset_params, feature_params, forecast_params, model_params, status='pending', message=None):
    return await fetchrow(
        """
        INSERT INTO jobs (
            job_id, branch_id, user_id, secret, 
            dataset_params, feature_engineering_params, 
            forecast_params, model_hyperparams, status, message
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        RETURNING job_id, secret, status, message, created_at;
        """,
        job_id, branch_id, user_id, secret,
        json.dumps(dataset_params), json.dumps(feature_params),
        json.dumps(forecast_params), json.dumps(model_params),
        status, message,
    )

async def get_job(job_id):
    return await fetchrow(
        "SELECT j.*, m.name as model_name FROM jobs j LEFT JOIN models m ON m.model_id = j.model_id WHERE j.job_id = $1;",
        job_id,
    )

async def get_jobs(group_id=None, status=None, limit=100):
    query = """
        SELECT j.*, m.name as model_name
        FROM jobs j JOIN branches b ON b.branch_id = j.branch_id
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
    return await fetch(query, *params)

async def update_job_status(job_id, status, result=None, message=None, model_id=None):
    if result is not None:
        return await fetchrow(
            """
            UPDATE jobs 
            SET status = $1, result = $2, message = COALESCE($3, message), model_id = COALESCE($4, model_id), updated_at = NOW()
            WHERE job_id = $5
            RETURNING job_id, status, message, model_id, updated_at;
            """,
            status, json.dumps(result), message,
            uuid.UUID(model_id) if isinstance(model_id, str) else model_id, job_id,
        )
    return await fetchrow(
        """
        UPDATE jobs 
        SET status = $1, message = COALESCE($2, message), model_id = COALESCE($3, model_id), updated_at = NOW()
        WHERE job_id = $4
        RETURNING job_id, status, message, model_id, updated_at;
        """,
        status, message,
        uuid.UUID(model_id) if isinstance(model_id, str) else model_id, job_id,
    )

async def verify_job_data_exists(branch_id: int, features: list, start_time, end_time):
    missing_features = []
    sensor_features = [f for f in features if f != "people"]
    for feat in sensor_features:
        count = await fetchrow(
            """
            SELECT COUNT(*) as count
            FROM values v JOIN sensors s ON s.sensor_id = v.sensor_id
            WHERE s.branch_id = $1 AND v.created_at BETWEEN $2 AND $3
              AND (v.value #>> '{}')::jsonb ? $4;
            """,
            branch_id, start_time, end_time, feat
        )
        if not count or count["count"] == 0:
            missing_features.append(feat)
    if "people" in features:
        count = await fetchrow(
            "SELECT COUNT(*) as count FROM image_analysis ia JOIN cameras c ON c.camera_id = ia.camera_id WHERE c.branch_id = $1 AND ia.created_at BETWEEN $2 AND $3;",
            branch_id, start_time, end_time
        )
        if not count or count["count"] == 0:
            missing_features.append("people")
    if missing_features:
        return False, f"Insufficient data for features: {', '.join(missing_features)}"
    return True, ""

async def cancel_job(job_id):
    return await fetchrow("UPDATE jobs SET status = 'cancelled', updated_at = NOW() WHERE job_id = $1 RETURNING job_id, status;", job_id)

async def get_or_create_model(group_id: int, model_id, name: str):
    return await fetchrow(
        """
        INSERT INTO models (model_id, group_id, name)
        VALUES ($1, $2, $3)
        ON CONFLICT (model_id) DO UPDATE SET name = EXCLUDED.name
        RETURNING model_id, name;
        """,
        uuid.UUID(model_id) if isinstance(model_id, str) else model_id, group_id, name,
    )

async def get_models(group_id: int):
    return await fetch("SELECT model_id, name, created_at FROM models WHERE group_id = $1 ORDER BY created_at DESC;", group_id)

async def update_model_name(model_id, name: str, group_id: int):
    return await fetchrow(
        "UPDATE models SET name = $1 WHERE model_id = $2 AND group_id = $3 RETURNING model_id, name;",
        name, uuid.UUID(model_id) if isinstance(model_id, str) else model_id, group_id
    )
