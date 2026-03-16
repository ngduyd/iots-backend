from fastapi import APIRouter, Depends, Query

from app.schemas import SensorListResponse, SensorStatus, SensorValue, SensorValueListResponse
from app.security import get_current_user
from app.services.database import get_sensor_values, get_sensors

router = APIRouter(prefix="/api/sensors", tags=["sensors"])


@router.get("", response_model=SensorListResponse)
async def list_sensors(
    limit: int = Query(default=100, ge=1, le=1000),
    _user: str = Depends(get_current_user),
):
    rows = await get_sensors(limit=limit)
    items = [
        SensorStatus(
            name=row["name"],
            status=row.get("status"),
            vbat=row.get("vbat"),
            updated_at=row.get("updated_at"),
        )
        for row in rows
    ]
    return SensorListResponse(count=len(items), items=items)


@router.get("/{sensor_name}/values", response_model=SensorValueListResponse)
async def list_sensor_values(
    sensor_name: str,
    limit: int = Query(default=100, ge=1, le=1000),
    _user: str = Depends(get_current_user),
):
    rows = await get_sensor_values(sensor_name=sensor_name, limit=limit)
    items = [
        SensorValue(
            type=row["type"],
            value=float(row["value"]),
            created_at=row["created_at"],
        )
        for row in rows
    ]
    return SensorValueListResponse(sensor=sensor_name, count=len(items), items=items)
