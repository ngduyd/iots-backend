from fastapi import APIRouter, Depends, HTTPException, Query

from app.schemas import SensorCreateRequest, SensorListResponse, SensorStatus, SensorValue, SensorValueListResponse, ResponseMessage
from app.security import get_current_user_record, is_superadmin, require_admin
from app.services.database import add_sensor as create_sensor, get_branch, get_sensor_values, get_sensors

router = APIRouter(prefix="/api/sensors", tags=["sensors"])


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


@router.get("/{sensor_name}/values", response_model=ResponseMessage)
async def list_sensor_values(
    sensor_name: str,
    limit: int = Query(default=100, ge=1, le=1000),
    current_user: dict = Depends(get_current_user_record),
):
    if not is_superadmin(current_user) and current_user.get("group_id") is None:
        raise HTTPException(status_code=403, detail="User is not assigned to any group")

    rows = await get_sensor_values(
        sensor_name=sensor_name,
        limit=limit,
        group_id=None if is_superadmin(current_user) else current_user.get("group_id"),
    )
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
        data=SensorValueListResponse(sensor=sensor_name, count=len(items), items=items),
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
            name=row.get("name"),
            status=row.get("status"),
            updated_at=row.get("updated_at"),
        ),
    )