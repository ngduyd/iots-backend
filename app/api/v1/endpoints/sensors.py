from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query

from app.schemas.sensor import SensorCreateRequest, SensorListResponse, SensorStatus, SensorValue, SensorValueListResponse
from app.schemas.common import ResponseMessage
from app.core import security
from app.services import sensor_service, branch_service

router = APIRouter()

@router.get("", response_model=ResponseMessage)
async def list_sensors(
    limit: int = Query(default=100, ge=1, le=1000),
    current_user: dict = Depends(security.get_current_user_record),
):
    if not security.is_superadmin(current_user) and current_user.get("group_id") is None:
        raise HTTPException(status_code=403, detail="User is not assigned to any group")

    rows = await sensor_service.get_sensors(
        limit=limit,
        group_id=None if security.is_superadmin(current_user) else current_user.get("group_id"),
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
    current_user: dict = Depends(security.get_current_user_record),
):
    if not security.is_superadmin(current_user) and current_user.get("group_id") is None:
        raise HTTPException(status_code=403, detail="User is not assigned to any group")

    row = await sensor_service.get_sensor(
        sensor_id=sensor_id,
        group_id=None if security.is_superadmin(current_user) else current_user.get("group_id"),
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
    limit: int = Query(default=1000000, ge=1, le=1000000),
    from_time: datetime | None = Query(default=None),
    to_time: datetime | None = Query(default=None),
    current_user: dict = Depends(security.get_current_user_record),
):
    if not security.is_superadmin(current_user) and current_user.get("group_id") is None:
        raise HTTPException(status_code=403, detail="User is not assigned to any group")

    if from_time is not None and to_time is not None and from_time > to_time:
        raise HTTPException(status_code=400, detail="from_time must be less than or equal to to_time")

    rows = await sensor_service.sensor_repo.get_sensor_values(
        sensor_id=sensor_id,
        limit=limit,
        group_id=None if security.is_superadmin(current_user) else current_user.get("group_id"),
        from_time=from_time,
        to_time=to_time,
    )

    sensor_name = await sensor_service.sensor_repo.get_sensor_name(sensor_id)

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
async def add_sensor(sensor: SensorCreateRequest, admin_user: dict = Depends(security.require_admin)):
    if not security.is_superadmin(admin_user) and admin_user.get("group_id") is None:
        raise HTTPException(status_code=403, detail="Admin user is not assigned to any group")

    branch = await branch_service.get_branch(
        sensor.branch_id,
        None if security.is_superadmin(admin_user) else admin_user.get("group_id"),
    )
    if not branch:
        raise HTTPException(status_code=403, detail="Permission denied")

    row = await sensor_service.add_sensor(
        name=sensor.name,
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
async def update_sensor(sensor_id: str, sensor: SensorCreateRequest, admin_user: dict = Depends(security.require_admin)):
    if not security.is_superadmin(admin_user) and admin_user.get("group_id") is None:
        raise HTTPException(status_code=403, detail="Admin user is not assigned to any group")

    existing_sensor = await sensor_service.get_sensor(
        sensor_id=sensor_id,
        group_id=None if security.is_superadmin(admin_user) else admin_user.get("group_id"),
    )
    if not existing_sensor:
        raise HTTPException(status_code=404, detail="Sensor not found")

    branch = await branch_service.get_branch(
        sensor.branch_id,
        None if security.is_superadmin(admin_user) else admin_user.get("group_id"),
    )
    if not branch:
        raise HTTPException(status_code=403, detail="Permission denied")

    row = await sensor_service.update_sensor(
        sensor_id=sensor_id,
        name=sensor.name,
        branch_id=sensor.branch_id,
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
async def delete_sensor(sensor_id: str, admin_user: dict = Depends(security.require_admin)):
    if not security.is_superadmin(admin_user) and admin_user.get("group_id") is None:
        raise HTTPException(status_code=403, detail="Admin user is not assigned to any group")

    existing_sensor = await sensor_service.get_sensor(
        sensor_id=sensor_id,
        group_id=None if security.is_superadmin(admin_user) else admin_user.get("group_id"),
    )
    if not existing_sensor:
        raise HTTPException(status_code=404, detail="Sensor not found")

    row = await sensor_service.update_sensor(
        sensor_id=sensor_id,
        delete=True,
    )
    if not row:
        raise HTTPException(status_code=400, detail="Cannot delete sensor")

    return ResponseMessage(
        code=200,
        message="Sensor deleted successfully",
    )
