from fastapi import APIRouter, Depends, HTTPException, Query

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
    get_branches as get_branches_db,
    get_cameras_by_branch as get_cameras_by_branch_db,
    get_sensors_by_branch as get_sensors_by_branch_db,
    update_branch as update_branch_db,
)

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