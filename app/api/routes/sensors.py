from datetime import datetime
import asyncio
import json
from urllib import error, request

from fastapi import APIRouter, Depends, HTTPException, Query
from app.core import config

from app.schemas import SensorCreateRequest, SensorListResponse, SensorStatus, SensorValue, SensorValueListResponse, ResponseMessage
from app.security import get_current_user_record, is_superadmin, require_admin
from app.services.database import add_sensor as create_sensor, get_branch, get_sensor, get_sensor_name, get_sensor_values, get_sensors, update_sensor as update_sensor_db

router = APIRouter(prefix="/api/sensors", tags=["sensors"])

PREDICT_API_URL = f"{config.AI_API_URL}/predict"
PREDICT_ROWS = 120
PREDICT_TIMEOUT_SECONDS = 20


@router.get("", response_model=ResponseMessage)
async def list_sensors(
    limit: int = Query(default=100, ge=1, le=1000),
    current_user: dict = Depends(get_current_user_record),
):
    if not is_superadmin(current_user) and current_user.get("group_id") is None:
        raise HTTPException(status_code=403, detail="User is not assigned to any group")

    rows = await get_sensors(
        limit=limit,
        group_id=None if is_superadmin(current_user) else current_user.get("group_id"),
    )
    items = [
        SensorStatus(
            sensor_id=row.get("sensor_id"),
            name=row["name"],
            status=row.get("status"),
            updated_at=row.get("updated_at"),
        )
        for row in rows
    ]
    return ResponseMessage(
        code=200,
        message="Sensors retrieved successfully",
        data=SensorListResponse(count=len(items), items=items),
    )


@router.get("/{sensor_id}", response_model=ResponseMessage)
async def get_sensor_by_id(
    sensor_id: str,
    current_user: dict = Depends(get_current_user_record),
):
    if not is_superadmin(current_user) and current_user.get("group_id") is None:
        raise HTTPException(status_code=403, detail="User is not assigned to any group")

    row = await get_sensor(
        sensor_id=sensor_id,
        group_id=None if is_superadmin(current_user) else current_user.get("group_id"),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Sensor not found")

    return ResponseMessage(
        code=200,
        message="Sensor retrieved successfully",
        data=SensorStatus(
            sensor_id=row.get("sensor_id"),
            name=row.get("name"),
            branch_id=row.get("branch_id"),
            status=row.get("status"),
            updated_at=row.get("updated_at"),
        ),
    )


@router.get("/{sensor_id}/values", response_model=ResponseMessage)
async def list_sensor_values(
    sensor_id: str,
    limit: int = Query(default=100, ge=1, le=1000),
    from_time: datetime | None = Query(default=None),
    to_time: datetime | None = Query(default=None),
    current_user: dict = Depends(get_current_user_record),
):
    if not is_superadmin(current_user) and current_user.get("group_id") is None:
        raise HTTPException(status_code=403, detail="User is not assigned to any group")

    if from_time is not None and to_time is not None and from_time > to_time:
        raise HTTPException(status_code=400, detail="from_time must be less than or equal to to_time")

    rows = await get_sensor_values(
        sensor_id=sensor_id,
        limit=limit,
        group_id=None if is_superadmin(current_user) else current_user.get("group_id"),
        from_time=from_time,
        to_time=to_time,
    )

    sensor_name = await get_sensor_name(sensor_id)

    items = [
        SensorValue(
            value=row["value"],
            created_at=row["created_at"],
        )
        for row in rows
    ]
    return ResponseMessage(
        code=200,
        message="Sensor values retrieved successfully",
        data=SensorValueListResponse(sensor_id=sensor_id, sensor_name=sensor_name, count=len(items), items=items),
    )

@router.post("", response_model=ResponseMessage)
async def add_sensor(sensor: SensorCreateRequest, admin_user: dict = Depends(require_admin)):
    if not is_superadmin(admin_user) and admin_user.get("group_id") is None:
        raise HTTPException(status_code=403, detail="Admin user is not assigned to any group")

    branch = await get_branch(
        sensor.branch_id,
        None if is_superadmin(admin_user) else admin_user.get("group_id"),
    )
    if not branch:
        raise HTTPException(status_code=403, detail="Permission denied")

    row = await create_sensor(
        sensor_name=sensor.name,
        branch_id=sensor.branch_id,
    )
    if not row:
        raise HTTPException(status_code=400, detail="Cannot create sensor")

    return ResponseMessage(
        code=200,
        message="Sensor created successfully",
        data=SensorStatus(
            sensor_id=row.get("sensor_id"),
            name=row.get("name"),
            branch_id=row.get("branch_id"),
            status=row.get("status"),
            updated_at=row.get("updated_at"),
        ),
    )

@router.put("/{sensor_id}", response_model=ResponseMessage)
async def update_sensor(sensor_id: str, sensor: SensorCreateRequest, admin_user: dict = Depends(require_admin)):
    if not is_superadmin(admin_user) and admin_user.get("group_id") is None:
        raise HTTPException(status_code=403, detail="Admin user is not assigned to any group")

    existing_sensor = await get_sensor(
        sensor_id=sensor_id,
        group_id=None if is_superadmin(admin_user) else admin_user.get("group_id"),
    )
    if not existing_sensor:
        raise HTTPException(status_code=404, detail="Sensor not found")

    branch = await get_branch(
        sensor.branch_id,
        None if is_superadmin(admin_user) else admin_user.get("group_id"),
    )
    if not branch:
        raise HTTPException(status_code=403, detail="Permission denied")

    row = await update_sensor_db(
        sensor_name=sensor.name,
        branch_id=sensor.branch_id,
        sensor_id=sensor_id,
    )
    if not row:
        raise HTTPException(status_code=400, detail="Cannot update sensor")

    return ResponseMessage(
        code=200,
        message="Sensor updated successfully",
        data=SensorStatus(
            sensor_id=row.get("sensor_id"),
            name=row.get("name"),
            branch_id=row.get("branch_id"),
            status=row.get("status"),
            updated_at=row.get("updated_at"),
        ),
    )

@router.delete("/{sensor_id}", response_model=ResponseMessage)
async def delete_sensor(sensor_id: str, admin_user: dict = Depends(require_admin)):
    if not is_superadmin(admin_user) and admin_user.get("group_id") is None:
        raise HTTPException(status_code=403, detail="Admin user is not assigned to any group")

    existing_sensor = await get_sensor(
        sensor_id=sensor_id,
        group_id=None if is_superadmin(admin_user) else admin_user.get("group_id"),
    )
    if not existing_sensor:
        raise HTTPException(status_code=404, detail="Sensor not found")

    row = await update_sensor_db(
        sensor_name=None,
        branch_id=None,
        sensor_id=sensor_id,
        delete=True,
    )
    if not row:
        raise HTTPException(status_code=400, detail="Cannot delete sensor")

    return ResponseMessage(
        code=200,
        message="Sensor deleted successfully",
    )

@router.get("/{sensor_id}/predict", response_model=ResponseMessage)
async def predict_sensor_values(
    sensor_id: str,
    current_user: dict = Depends(get_current_user_record),
):
    if not is_superadmin(current_user) and current_user.get("group_id") is None:
        raise HTTPException(status_code=403, detail="User is not assigned to any group")

    existing_sensor = await get_sensor(
        sensor_id=sensor_id,
        group_id=None if is_superadmin(current_user) else current_user.get("group_id"),
    )
    if not existing_sensor:
        raise HTTPException(status_code=404, detail="Sensor not found")

    rows = await get_sensor_values(
        sensor_id=sensor_id,
        limit=PREDICT_ROWS,
        group_id=None if is_superadmin(current_user) else current_user.get("group_id"),
    )
    if len(rows) < PREDICT_ROWS:
        raise HTTPException(
            status_code=400,
            detail=f"Not enough data to predict. Required {PREDICT_ROWS} rows, got {len(rows)}",
        )

    chronological_rows = list(reversed(rows))
    values = [
        {
            "value": str(row["value"]) if row.get("value") is not None else None,
            "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        }
        for row in chronological_rows
    ]

    sensor_model_id = existing_sensor.get("model_id") or "default"

    payload = {
        "senser_id": sensor_id,
        "rows": values,
        "model_id": sensor_model_id,
    }

    req = request.Request(
        PREDICT_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        response_text = await asyncio.to_thread(_send_predict_request, req)
        prediction_data = json.loads(response_text) if response_text else None
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        raise HTTPException(
            status_code=502,
            detail=f"Prediction service returned HTTP {exc.code}: {body}",
        )
    except error.URLError as exc:
        raise HTTPException(status_code=502, detail=f"Cannot connect to prediction service: {exc.reason}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=502, detail="Prediction service returned invalid JSON")

    return ResponseMessage(
        code=200,
        message="Prediction completed successfully",
        data=prediction_data,
    )


def _send_predict_request(req: request.Request) -> str:
    with request.urlopen(req, timeout=PREDICT_TIMEOUT_SECONDS) as response:
        return response.read().decode("utf-8")
