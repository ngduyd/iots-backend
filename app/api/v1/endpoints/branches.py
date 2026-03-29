import csv
import io
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.schemas.branch import BranchCreateByAdminRequest, BranchUpdateRequest
from app.schemas.camera import CameraListResponse, CameraResponse
from app.schemas.sensor import SensorListResponse, SensorStatus
from app.schemas.common import ResponseMessage
from app.core import security
from app.services import branch_service, sensor_service, camera_service, prediction_service
from app.workers import runtime

router = APIRouter()

@router.get("", response_model=ResponseMessage)
async def list_branches(current_user: dict = Depends(security.get_current_user_record)):
    if not security.is_superadmin(current_user) and current_user.get("group_id") is None:
        # If user has no group and not superadmin, they shouldn't see anything or 403
        raise HTTPException(status_code=403, detail="User is not assigned to any group")

    if security.is_superadmin(current_user):
        branches = await branch_service.get_branches()
    else:
        branches = await branch_service.get_branches(group_id=current_user.get("group_id"))

    return ResponseMessage(
        code=200,
        message="Branches retrieved successfully",
        data=branches
    )

@router.get("/{branch_id}", response_model=ResponseMessage)
async def get_branch(branch_id: int, current_user: dict = Depends(security.get_current_user_record)):
    if not security.is_superadmin(current_user) and current_user.get("group_id") is None:
        raise HTTPException(status_code=403, detail="User is not assigned to any group")

    row = await branch_service.get_branch(
        branch_id,
        None if security.is_superadmin(current_user) else current_user.get("group_id"),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Branch not found")
    return ResponseMessage(
        code=200,
        message="Branch retrieved successfully",
        data=row
    )

@router.get("/{branch_id}/sensors", response_model=ResponseMessage)
async def list_branch_sensors(
    branch_id: int,
    limit: int = Query(default=100, ge=1, le=1000),
    current_user: dict = Depends(security.get_current_user_record),
):
    if not security.is_superadmin(current_user) and current_user.get("group_id") is None:
        raise HTTPException(status_code=403, detail="User is not assigned to any group")

    branch = await branch_service.get_branch(
        branch_id,
        None if security.is_superadmin(current_user) else current_user.get("group_id"),
    )
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")

    rows = await sensor_service.sensor_repo.get_sensors_by_branch(branch_id=branch_id, limit=limit)
    items = [
        SensorStatus(
            sensor_id=row.get("sensor_id"),
            name=row.get("name"),
            status=row.get("status"),
            updated_at=row.get("updated_at"),
        )
        for row in rows
    ]
    return ResponseMessage(
        code=200,
        message="Branch sensors retrieved successfully",
        data=SensorListResponse(count=len(items), items=items),
    )

@router.get("/{branch_id}/cameras", response_model=ResponseMessage)
async def list_branch_cameras(
    branch_id: int,
    limit: int = Query(default=100, ge=1, le=1000),
    current_user: dict = Depends(security.get_current_user_record),
):
    if not security.is_superadmin(current_user) and current_user.get("group_id") is None:
        raise HTTPException(status_code=403, detail="User is not assigned to any group")

    branch = await branch_service.get_branch(
        branch_id,
        None if security.is_superadmin(current_user) else current_user.get("group_id"),
    )
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")
    
    rows = await camera_service.camera_repo.get_cameras_by_branch(branch_id=branch_id, limit=limit)
    items = [
        CameraResponse(
            camera_id=row.get("camera_id"),
            branch_id=row.get("branch_id"),
            name=row.get("name"),
            secret=row.get("secret"),
            created_at=row.get("created_at"),
        )
        for row in rows
    ]
    return ResponseMessage(
        code=200,
        message="Branch cameras retrieved successfully",
        data=CameraListResponse(count=len(items), items=items),
    )

@router.post("", response_model=ResponseMessage)
async def create_branch(
    branch: BranchCreateByAdminRequest,
    admin_user: dict = Depends(security.require_admin),
):
    if not security.is_superadmin(admin_user) and admin_user.get("group_id") is None:
        raise HTTPException(status_code=403, detail="Admin user is not assigned to any group")

    if security.is_superadmin(admin_user) and branch.group_id is None:
        raise HTTPException(status_code=400, detail="group_id is required for superadmin")

    group_id = branch.group_id if security.is_superadmin(admin_user) else admin_user.get("group_id")
    row = await branch_service.create_branch(
        group_id=group_id,
        name=branch.name,
        thresholds=branch.thresholds,
    )
    if not row:
        raise HTTPException(status_code=400, detail="Cannot create branch")
    return ResponseMessage(
        code=200,
        message="Branch created successfully",
        data=row
    )

@router.put("/{branch_id}", response_model=ResponseMessage)
async def update_branch(
    branch_id: int,
    branch: BranchUpdateRequest,
    admin_user: dict = Depends(security.require_admin),
):
    if not security.is_superadmin(admin_user) and admin_user.get("group_id") is None:
        raise HTTPException(status_code=403, detail="Admin user is not assigned to any group")

    existing = await branch_service.get_branch(
        branch_id,
        None if security.is_superadmin(admin_user) else admin_user.get("group_id"),
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Branch not found")

    target_group_id = branch.group_id if security.is_superadmin(admin_user) and branch.group_id is not None else existing["group_id"]
    target_name = branch.name if branch.name else existing["name"]
    target_thresholds = branch.thresholds if branch.thresholds is not None else existing["thresholds"]

    row = await branch_service.update_branch(
        branch_id=branch_id,
        group_id=target_group_id,
        name=target_name,
        thresholds=target_thresholds,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Branch not found")

    # Sync with MQTT Runtime cache
    runtime.update_threshold_cache(branch_id, target_thresholds)

    return ResponseMessage(
        code=200,
        message="Branch updated successfully",
        data=row
    )

@router.delete("/{branch_id}", response_model=ResponseMessage)
async def delete_branch(branch_id: int, admin_user: dict = Depends(security.require_admin)):
    if not security.is_superadmin(admin_user) and admin_user.get("group_id") is None:
        raise HTTPException(status_code=403, detail="Admin user is not assigned to any group")

    existing = await branch_service.get_branch(
        branch_id,
        None if security.is_superadmin(admin_user) else admin_user.get("group_id"),
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Branch not found")

    deleted = await branch_service.delete_branch(branch_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Branch not found")
    return ResponseMessage(
        code=200,
        message="Branch deleted successfully",
        data=None
    )

@router.get("/{branch_id}/predict", response_model=ResponseMessage)
async def predict_branch(
    branch_id: int,
    current_user: dict = Depends(security.get_current_user_record),
):
    if not security.is_superadmin(current_user) and current_user.get("group_id") is None:
        raise HTTPException(status_code=403, detail="User is not assigned to any group")

    branch = await branch_service.get_branch(
        branch_id,
        None if security.is_superadmin(current_user) else current_user.get("group_id"),
    )
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")

    camera = await camera_service.camera_repo.get_camera_by_branch(branch_id)
    if not camera or camera.get("status") != "online":
        raise HTTPException(
            status_code=400,
            detail="Branch does not have an online camera. Cannot predict.",
        )

    sensors = await sensor_service.sensor_repo.get_sensors_by_branch(branch_id=branch_id, limit=1)
    if not sensors:
        raise HTTPException(status_code=400, detail="Branch has no sensors")
    sensor = sensors[0]
    sensor_id = sensor["sensor_id"]

    PREDICT_ROWS = 125
    rows = await sensor_service.sensor_repo.get_sensor_values(sensor_id=sensor_id, limit=PREDICT_ROWS)
    if len(rows) < PREDICT_ROWS:
        raise HTTPException(
            status_code=400,
            detail=f"Not enough sensor data. Required {PREDICT_ROWS} rows, got {len(rows)}.",
        )

    people_rows = await camera_service.camera_repo.get_latest_people_count_by_branch(branch_id)
    people = [
        {
            "value": row["people_count"],
            "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        }
        for row in people_rows
    ] if people_rows else []

    chronological_rows = list(reversed(rows))
    values = [
        {
            "value": str(row["value"]) if row.get("value") is not None else None,
            "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        }
        for row in chronological_rows
    ]

    try:
        prediction_data = await prediction_service.predict_branch(sensor_id, values, people)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

    return ResponseMessage(
        code=200,
        message="Prediction completed successfully",
        data={
            "prediction": prediction_data,
        },
    )

@router.get("/{branch_id}/alerts", response_model=ResponseMessage)
async def list_branch_alerts(
    branch_id: int,
    limit: int = Query(10, ge=1, le=100),
    unread_only: bool = Query(False),
    current_user: dict = Depends(security.get_current_user_record),
):
    if not security.is_superadmin(current_user) and current_user.get("group_id") is None:
        raise HTTPException(status_code=403, detail="User is not assigned to any group")

    branch = await branch_service.get_branch(
        branch_id,
        None if security.is_superadmin(current_user) else current_user.get("group_id"),
    )
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")

    alerts = await branch_service.get_alerts_by_branch(branch_id, limit=limit, unread_only=unread_only)
    return ResponseMessage(
        code=200,
        message="Alerts retrieved successfully",
        data=alerts,
    )

@router.post("/{branch_id}/alerts/{alert_id}/read", response_model=ResponseMessage)
async def mark_alert_as_read(
    alert_id: int,
    current_user: dict = Depends(security.get_current_user_record),
):
    updated = await branch_service.mark_alert_as_read(alert_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Alert not found")
        
    return ResponseMessage(code=200, message="Alert marked as read", data=updated)

@router.get("/{branch_id}/export")
async def export_branch_data(
    branch_id: int,
    from_time: datetime = Query(...),
    to_time: datetime = Query(...),
    current_user: dict = Depends(security.get_current_user_record),
):
    if not security.is_superadmin(current_user) and current_user.get("group_id") is None:
        raise HTTPException(status_code=403, detail="User is not assigned to any group")

    branch = await branch_service.get_branch(
        branch_id,
        None if security.is_superadmin(current_user) else current_user.get("group_id"),
    )
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")

    sensor_values, people_counts = await branch_service.branch_repo.get_branch_data_for_export(branch_id, from_time, to_time)

    extra_keys = set()
    for row in sensor_values:
        if isinstance(row["value"], dict):
            extra_keys.update(row["value"].keys())
    sorted_keys = sorted(list(extra_keys))

    def get_closest_people_count(sensor_ts):
        if not people_counts:
            return ""
        closest = min(people_counts, key=lambda x: abs((x["created_at"] - sensor_ts).total_seconds()))
        if abs((closest["created_at"] - sensor_ts).total_seconds()) < 30:
            return closest["people_count"]
        return ""

    def generate_csv():
        output = io.StringIO()
        writer = csv.writer(output)
        
        header = ["Time", "Sensor ID", "Sensor Name"] + sorted_keys + ["People Count"]
        writer.writerow(header)
        yield output.getvalue()
        output.truncate(0)
        output.seek(0)

        for row in sensor_values:
            ts = row["created_at"]
            val_obj = row["value"]
            
            csv_row = [
                ts.strftime("%Y-%m-%d %H:%M:%S"),
                row["sensor_id"],
                row["sensor_name"],
            ]
            
            for key in sorted_keys:
                csv_row.append(val_obj.get(key, "") if isinstance(val_obj, dict) else "")
            
            csv_row.append(get_closest_people_count(ts))
            
            writer.writerow(csv_row)
            yield output.getvalue()
            output.truncate(0)
            output.seek(0)

    filename = f"branch_{branch_id}_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        generate_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
