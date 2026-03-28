import asyncio
import csv
import io
import json
from datetime import datetime
from urllib import error, request

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.core import config
from app.schemas import (
    BranchCreateByAdminRequest,
    BranchCreateRequest,
    CameraListResponse,
    CameraResponse,
    ResponseMessage,
    SensorListResponse,
    SensorStatus,
)
from app.security import get_current_user_record, is_superadmin, require_admin
from app.services.database import (
    create_branch as create_branch_db,
    delete_branch as delete_branch_db,
    get_branch as get_branch_db,
    get_branch_data_for_export,
    get_branches as get_branches_db,
    get_camera_by_branch as get_camera_by_branch_db,
    get_cameras_by_branch as get_cameras_by_branch_db,
    get_latest_people_count_by_branch,
    get_sensor_values,
    get_sensors_by_branch as get_sensors_by_branch_db,
    update_branch as update_branch_db,
)

PREDICT_API_URL = f"{config.AI_API_URL}/predict"
PREDICT_ROWS = 125
PREDICT_TIMEOUT_SECONDS = 20

router = APIRouter(prefix="/api/branches", tags=["branches"])


@router.get("", response_model=ResponseMessage)
async def list_branches(current_user: dict = Depends(get_current_user_record)):
    if not is_superadmin(current_user) and current_user.get("group_id") is None:
        raise HTTPException(status_code=403, detail="User is not assigned to any group")

    if is_superadmin(current_user):
        branches = await get_branches_db()
    else:
        branches = await get_branches_db(group_id=current_user.get("group_id"))

    return ResponseMessage(
        code=200,
        message="Branches retrieved successfully",
        data=branches
    )


@router.get("/{branch_id}", response_model=ResponseMessage)
async def get_branch(branch_id: int, current_user: dict = Depends(get_current_user_record)):
    if not is_superadmin(current_user) and current_user.get("group_id") is None:
        raise HTTPException(status_code=403, detail="User is not assigned to any group")

    row = await get_branch_db(
        branch_id,
        None if is_superadmin(current_user) else current_user.get("group_id"),
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
    current_user: dict = Depends(get_current_user_record),
):
    if not is_superadmin(current_user) and current_user.get("group_id") is None:
        raise HTTPException(status_code=403, detail="User is not assigned to any group")

    branch = await get_branch_db(
        branch_id,
        None if is_superadmin(current_user) else current_user.get("group_id"),
    )
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")

    rows = await get_sensors_by_branch_db(branch_id=branch_id, limit=limit)
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
    current_user: dict = Depends(get_current_user_record),
):
    if not is_superadmin(current_user) and current_user.get("group_id") is None:
        raise HTTPException(status_code=403, detail="User is not assigned to any group")

    branch = await get_branch_db(
        branch_id,
        None if is_superadmin(current_user) else current_user.get("group_id"),
    )
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")
    
    rows = await get_cameras_by_branch_db(branch_id=branch_id, limit=limit)
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
    admin_user: dict = Depends(require_admin),
):
    if not is_superadmin(admin_user) and admin_user.get("group_id") is None:
        raise HTTPException(status_code=403, detail="Admin user is not assigned to any group")

    if is_superadmin(admin_user) and branch.group_id is None:
        raise HTTPException(status_code=400, detail="group_id is required for superadmin")

    group_id = branch.group_id if is_superadmin(admin_user) else admin_user.get("group_id")
    row = await create_branch_db(
        group_id=group_id,
        name=branch.name,
        alert=branch.alert,
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
    branch: BranchCreateRequest,
    admin_user: dict = Depends(require_admin),
):
    if not is_superadmin(admin_user) and admin_user.get("group_id") is None:
        raise HTTPException(status_code=403, detail="Admin user is not assigned to any group")

    existing = await get_branch_db(
        branch_id,
        None if is_superadmin(admin_user) else admin_user.get("group_id"),
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Branch not found")

    target_group_id = branch.group_id if is_superadmin(admin_user) else admin_user.get("group_id")

    row = await update_branch_db(
        branch_id=branch_id,
        group_id=target_group_id,
        name=branch.name,
        alert=branch.alert,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Branch not found")
    return ResponseMessage(
        code=200,
        message="Branch updated successfully",
        data=row
    )


@router.delete("/{branch_id}", response_model=ResponseMessage)
async def delete_branch(branch_id: int, admin_user: dict = Depends(require_admin)):
    if not is_superadmin(admin_user) and admin_user.get("group_id") is None:
        raise HTTPException(status_code=403, detail="Admin user is not assigned to any group")

    existing = await get_branch_db(
        branch_id,
        None if is_superadmin(admin_user) else admin_user.get("group_id"),
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Branch not found")

    deleted = await delete_branch_db(branch_id)
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
    current_user: dict = Depends(get_current_user_record),
):
    if not is_superadmin(current_user) and current_user.get("group_id") is None:
        raise HTTPException(status_code=403, detail="User is not assigned to any group")

    # Check branch access
    branch = await get_branch_db(
        branch_id,
        None if is_superadmin(current_user) else current_user.get("group_id"),
    )
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")

    # Check branch has an online camera
    camera = await get_camera_by_branch_db(branch_id)
    if not camera or camera.get("status") != "online":
        raise HTTPException(
            status_code=400,
            detail="Branch does not have an online camera. Cannot predict.",
        )

    # Get sensors of the branch, use the first one for prediction
    sensors = await get_sensors_by_branch_db(branch_id=branch_id, limit=1)
    if not sensors:
        raise HTTPException(status_code=400, detail="Branch has no sensors")
    sensor = sensors[0]
    sensor_id = sensor["sensor_id"]

    # Check sensor has enough data
    rows = await get_sensor_values(sensor_id=sensor_id, limit=PREDICT_ROWS)
    if len(rows) < PREDICT_ROWS:
        raise HTTPException(
            status_code=400,
            detail=f"Not enough sensor data. Required {PREDICT_ROWS} rows, got {len(rows)}.",
        )

    # Get people count records from the last 10 minutes
    people_rows = await get_latest_people_count_by_branch(branch_id)
    people = [
        {
            "value": row["people_count"],
            "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        }
        for row in people_rows
    ] if people_rows else []

    # Build payload
    chronological_rows = list(reversed(rows))
    values = [
        {
            "value": str(row["value"]) if row.get("value") is not None else None,
            "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        }
        for row in chronological_rows
    ]

    payload = {
        "senser_id": sensor_id,
        "rows": values,
        "model_id": "default",
        "people": people,
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
        data={
            "prediction": prediction_data,
        },
    )


@router.get("/{branch_id}/export")
async def export_branch_data(
    branch_id: int,
    from_time: datetime = Query(...),
    to_time: datetime = Query(...),
    current_user: dict = Depends(get_current_user_record),
):
    """Export branch sensor data and people count to CSV."""
    if not is_superadmin(current_user) and current_user.get("group_id") is None:
        raise HTTPException(status_code=403, detail="User is not assigned to any group")

    branch = await get_branch_db(
        branch_id,
        None if is_superadmin(current_user) else current_user.get("group_id"),
    )
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")

    sensor_values, people_counts = await get_branch_data_for_export(branch_id, from_time, to_time)

    # Determine all unique keys in JSON values across all sensors to create columns
    extra_keys = set()
    for row in sensor_values:
        if isinstance(row["value"], dict):
            extra_keys.update(row["value"].keys())
    sorted_keys = sorted(list(extra_keys))

    # Threshold-based matching for people counts (match to nearest sensor reading if within 30s)
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

    filename = f"branch_{branch_id}_export_{datetime.now().strftime('%Y% Lakewood%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        generate_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )



def _send_predict_request(req: request.Request) -> str:
    with request.urlopen(req, timeout=PREDICT_TIMEOUT_SECONDS) as response:
        return response.read().decode("utf-8")