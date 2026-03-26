from fastapi import APIRouter, Depends, HTTPException, Query, Form

from app.schemas import (
    CameraCreateRequest,
    CameraListResponse,
    CameraResponse,
    CameraVerifyStreamRequest,
    ResponseMessage,
)
from app.security import get_current_user_record, is_superadmin, require_admin
from app.core import config
from app.services.database import (
    add_camera as create_camera_db,
    create_camera_access_request as create_camera_access_request_db,
    delete_camera as delete_camera_db,
    get_branch,
    get_camera as get_camera_db,
    get_cameras as get_cameras_db,
    reset_camera_secret as reset_camera_secret_db,
    update_camera as update_camera_db,
    verify_camera_access_request as verify_camera_access_request_db,
    verify_camera_stream as verify_camera_stream_db,
)

from app.core import config

router = APIRouter(prefix="/api/cameras", tags=["cameras"])


@router.post("/verify-stream", response_model=ResponseMessage)
async def verify_stream(
    id: str = Form(alias="id"),
    secret: str = Form(default=None),
):
    row = await verify_camera_stream_db(camera_id=id, secret=secret)
    print(f"verify_stream: id={id}, secret={secret}, row={row}")
    if not row:
        raise HTTPException(status_code=403, detail="Invalid stream credentials")

    return ResponseMessage(
        code=200,
        message="Stream credentials verified",
    )


@router.get("/request-access", response_model=ResponseMessage)
async def request_camera_access(
    camera_id: str,
    current_user: dict = Depends(get_current_user_record),
):
    if not is_superadmin(current_user) and current_user.get("group_id") is None:
        raise HTTPException(status_code=403, detail="User is not assigned to any group")

    camera = await get_camera_db(
        camera_id=camera_id,
        group_id=None if is_superadmin(current_user) else current_user.get("group_id"),
    )
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    user_id = current_user.get("user_id")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid user session")

    access = await create_camera_access_request_db(
        camera_id=camera_id,
        user_id=user_id,
        ttl_seconds=config.CAMERA_ACCESS_TOKEN_TTL_SECONDS,
    )
    if not access:
        raise HTTPException(status_code=400, detail="Cannot create camera access token")

    token = access.get("access_token")
    stream_url = f"http://{config.SERVER_HOST_NAME}/hls/{camera_id}.m3u8?token={token}"

    return ResponseMessage(
        code=200,
        message="Camera access token created",
        data={
            "camera_id": camera_id,
            "access_token": token,
            "expires_at": access.get("expires_at"),
            "stream_url": stream_url,
        },
    )


@router.get("/verify-access", response_model=ResponseMessage)
async def verify_camera_access(
    camera_id: str,
    token: str,
    current_user: dict = Depends(get_current_user_record),
):
    if not is_superadmin(current_user) and current_user.get("group_id") is None:
        raise HTTPException(status_code=403, detail="User is not assigned to any group")

    camera = await get_camera_db(
        camera_id=camera_id,
        group_id=None if is_superadmin(current_user) else current_user.get("group_id"),
    )
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    user_id = current_user.get("user_id")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid user session")

    access = await verify_camera_access_request_db(
        camera_id=camera_id,
        access_token=token,
        user_id=user_id,
    )
    if not access:
        raise HTTPException(status_code=403, detail="Invalid or expired access token")

    return ResponseMessage(
        code=200,
        message="Camera access verified",
        data={
            "camera_id": camera_id,
            "expires_at": access.get("expires_at"),
            "status": access.get("status"),
        },
    )


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
            secret=row.get("secret"),
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
    camera_id: str,
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
            secret=row.get("secret"),
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
            secret=row.get("secret"),
            created_at=row.get("created_at"),
        ),
    )


@router.put("/{camera_id}", response_model=ResponseMessage)
async def update_camera(
    camera_id: str,
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
            secret=row.get("secret"),
            created_at=row.get("created_at"),
        ),
    )


@router.post("/{camera_id}/reset-secret", response_model=ResponseMessage)
async def reset_camera_secret(
    camera_id: str,
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

    row = await reset_camera_secret_db(camera_id=camera_id)
    if not row:
        raise HTTPException(status_code=400, detail="Cannot reset camera secret")

    return ResponseMessage(
        code=200,
        message="Camera secret reset successfully",
        data=CameraResponse(
            camera_id=row.get("camera_id"),
            branch_id=row.get("branch_id"),
            name=row.get("name"),
            secret=row.get("secret"),
            created_at=row.get("created_at"),
        ),
    )


@router.delete("/{camera_id}", response_model=ResponseMessage)
async def delete_camera(camera_id: str, admin_user: dict = Depends(require_admin)):
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
