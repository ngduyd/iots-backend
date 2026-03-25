from fastapi import APIRouter, Depends, HTTPException, Query

from app.schemas import CameraCreateRequest, CameraListResponse, CameraResponse, ResponseMessage
from app.security import get_current_user_record, is_superadmin, require_admin
from app.services.database import (
    add_camera as create_camera_db,
    delete_camera as delete_camera_db,
    get_branch,
    get_camera as get_camera_db,
    get_cameras as get_cameras_db,
    update_camera as update_camera_db,
)

router = APIRouter(prefix="/api/cameras", tags=["cameras"])


@router.get("", response_model=ResponseMessage)
async def list_cameras(
    limit: int = Query(default=100, ge=1, le=1000),
    current_user: dict = Depends(get_current_user_record),
):
    if not is_superadmin(current_user) and current_user.get("group_id") is None:
        raise HTTPException(status_code=403, detail="User is not assigned to any group")

    rows = await get_cameras_db(
        limit=limit,
        group_id=None if is_superadmin(current_user) else current_user.get("group_id"),
    )

    items = [
        CameraResponse(
            camera_id=row.get("camera_id"),
            branch_id=row.get("branch_id"),
            name=row.get("name"),
            ip_address=row.get("ip_address"),
            username=row.get("username"),
            created_at=row.get("created_at"),
        )
        for row in rows
    ]

    return ResponseMessage(
        code=200,
        message="Cameras retrieved successfully",
        data=CameraListResponse(count=len(items), items=items),
    )


@router.get("/{camera_id}", response_model=ResponseMessage)
async def get_camera(
    camera_id: int,
    current_user: dict = Depends(get_current_user_record),
):
    if not is_superadmin(current_user) and current_user.get("group_id") is None:
        raise HTTPException(status_code=403, detail="User is not assigned to any group")

    row = await get_camera_db(
        camera_id=camera_id,
        group_id=None if is_superadmin(current_user) else current_user.get("group_id"),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Camera not found")

    return ResponseMessage(
        code=200,
        message="Camera retrieved successfully",
        data=CameraResponse(
            camera_id=row.get("camera_id"),
            branch_id=row.get("branch_id"),
            name=row.get("name"),
            ip_address=row.get("ip_address"),
            username=row.get("username"),
            created_at=row.get("created_at"),
        ),
    )


@router.post("", response_model=ResponseMessage)
async def add_camera(camera: CameraCreateRequest, admin_user: dict = Depends(require_admin)):
    if not is_superadmin(admin_user) and admin_user.get("group_id") is None:
        raise HTTPException(status_code=403, detail="Admin user is not assigned to any group")

    branch = await get_branch(
        camera.branch_id,
        None if is_superadmin(admin_user) else admin_user.get("group_id"),
    )
    if not branch:
        raise HTTPException(status_code=403, detail="Permission denied")

    row = await create_camera_db(
        name=camera.name,
        branch_id=camera.branch_id,
        ip_address=camera.ip_address,
        username=camera.username,
        password=camera.password,
    )
    if not row:
        raise HTTPException(status_code=400, detail="Cannot create camera")

    return ResponseMessage(
        code=200,
        message="Camera created successfully",
        data=CameraResponse(
            camera_id=row.get("camera_id"),
            branch_id=row.get("branch_id"),
            name=row.get("name"),
            ip_address=row.get("ip_address"),
            username=row.get("username"),
            created_at=row.get("created_at"),
        ),
    )


@router.put("/{camera_id}", response_model=ResponseMessage)
async def update_camera(
    camera_id: int,
    camera: CameraCreateRequest,
    admin_user: dict = Depends(require_admin),
):
    if not is_superadmin(admin_user) and admin_user.get("group_id") is None:
        raise HTTPException(status_code=403, detail="Admin user is not assigned to any group")

    existing_camera = await get_camera_db(
        camera_id=camera_id,
        group_id=None if is_superadmin(admin_user) else admin_user.get("group_id"),
    )
    if not existing_camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    branch = await get_branch(
        camera.branch_id,
        None if is_superadmin(admin_user) else admin_user.get("group_id"),
    )
    if not branch:
        raise HTTPException(status_code=403, detail="Permission denied")

    row = await update_camera_db(
        camera_id=camera_id,
        name=camera.name,
        branch_id=camera.branch_id,
        ip_address=camera.ip_address,
        username=camera.username,
        password=camera.password,
    )
    if not row:
        raise HTTPException(status_code=400, detail="Cannot update camera")

    return ResponseMessage(
        code=200,
        message="Camera updated successfully",
        data=CameraResponse(
            camera_id=row.get("camera_id"),
            branch_id=row.get("branch_id"),
            name=row.get("name"),
            ip_address=row.get("ip_address"),
            username=row.get("username"),
            created_at=row.get("created_at"),
        ),
    )


@router.delete("/{camera_id}", response_model=ResponseMessage)
async def delete_camera(camera_id: int, admin_user: dict = Depends(require_admin)):
    if not is_superadmin(admin_user) and admin_user.get("group_id") is None:
        raise HTTPException(status_code=403, detail="Admin user is not assigned to any group")

    existing_camera = await get_camera_db(
        camera_id=camera_id,
        group_id=None if is_superadmin(admin_user) else admin_user.get("group_id"),
    )
    if not existing_camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    deleted = await delete_camera_db(camera_id=camera_id)
    if not deleted:
        raise HTTPException(status_code=400, detail="Cannot delete camera")

    return ResponseMessage(
        code=200,
        message="Camera deleted successfully",
    )
