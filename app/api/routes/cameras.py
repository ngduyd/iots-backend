from fastapi import APIRouter, Depends, HTTPException, Query, Form, Header
from typing import Optional

from urllib.parse import parse_qs, urlparse


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
    verify_camera_access_request_by_token as verify_camera_access_by_token_db,
    verify_camera_stream as verify_camera_stream_db,
    update_camera_status as update_camera_status_db,
    end_camera_stream as end_camera_stream_db,
)
from app.runtime import runtime

router = APIRouter(prefix="/api/cameras", tags=["cameras"])


@router.post("/verify-stream", response_model=ResponseMessage)
async def verify_stream(
    id: str = Form(alias="name"),
    secret: str = Form(default=None),
):
    row = await verify_camera_stream_db(camera_id=id, secret=secret)
    if not row:
        raise HTTPException(status_code=403, detail="Invalid stream credentials")
    runtime.add_camera_to_schedule(id)

    return ResponseMessage(
        code=200,
        message="Stream credentials verified",
    )


@router.post("/end-stream", response_model=ResponseMessage)
async def end_stream(
    camera_id: str = Form(alias="name"),
    secret: str = Form(default=None),
):
    row = await end_camera_stream_db(camera_id=camera_id, secret=secret)
    if not row:
        raise HTTPException(status_code=403, detail="Invalid stream credentials")

    runtime.remove_camera_from_schedule(camera_id)

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
    base_url = config.STREAM_BASE_URL.strip()
    stream_url = f"{base_url.rstrip('/')}/hls/{camera_id}.m3u8?token={token}"

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


@router.get("/verify-access")
async def verify_camera_access(
    query_string: Optional[str] = Header(default=None, alias="X-Query-String"),
    original_uri: Optional[str] = Header(default=None, alias="X-Original-URI")
):
    if original_uri:
        path = urlparse(original_uri).path
        if path.endswith(".ts"):
            return {"status": "TS chunk allowed"}

    token = None
    if query_string:
        parsed = parse_qs(query_string)
        token = parsed.get("token", [None])[0]

    if not token:
        raise HTTPException(status_code=403, detail="Access token is required")

    access = await verify_camera_access_by_token_db(
        access_token=token,
        ttl_seconds=config.CAMERA_ACCESS_TOKEN_TTL_SECONDS,
    )
    if not access:
        raise HTTPException(status_code=403, detail="Invalid or expired access token")

    return {
        "code": 200,
        "message": "Camera access verified",
        "data": {
            "camera_id": access.get("camera_id"),
            "expires_at": access.get("expires_at"),
            "status": access.get("status"),
        },
    }


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
            active=row.get("active", False),
            status=row.get("status", "offline"),
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
            active=row.get("active", False),
            status=row.get("status", "offline"),
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
        active=bool(camera.active) if camera.active is not None else False,
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
            active=row.get("active", False),
            status=row.get("status", "offline"),
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
        active=camera.active,
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
            active=row.get("active", False),
            status=row.get("status", "offline"),
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
            active=row.get("active", False),
            status=row.get("status", "offline"),
            created_at=row.get("created_at"),
        ),
    )


@router.post("/{camera_id}/active", response_model=ResponseMessage)
async def set_camera_active(
    camera_id: str,
    active: bool = Query(...),
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

    row = await update_camera_db(
        camera_id=camera_id,
        active=active,
    )
    if not row:
        raise HTTPException(status_code=400, detail="Cannot update camera active status")

    return ResponseMessage(
        code=200,
        message="Camera active status updated successfully",
        data=CameraResponse(
            camera_id=row.get("camera_id"),
            branch_id=row.get("branch_id"),
            name=row.get("name"),
            secret=row.get("secret"),
            active=row.get("active", False),
            status=row.get("status", "offline"),
            created_at=row.get("created_at"),
        ),
    )


@router.post("/{camera_id}/status", response_model=ResponseMessage)
async def set_camera_status(
    camera_id: str,
    status: str = Query(...),
):
    # This route might be called by an internal AI server or stream server.
    # Optionally add admin checking if needed, but for internal callbacks it might just need the camera_id.
    existing_camera = await get_camera_db(camera_id=camera_id)
    if not existing_camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    await update_camera_status_db(camera_id=camera_id, status=status)

    updated_camera = await get_camera_db(camera_id=camera_id)

    return ResponseMessage(
        code=200,
        message="Camera status updated successfully",
        data=CameraResponse(
            camera_id=updated_camera.get("camera_id"),
            branch_id=updated_camera.get("branch_id"),
            name=updated_camera.get("name"),
            secret=updated_camera.get("secret"),
            active=updated_camera.get("active", False),
            status=updated_camera.get("status", "offline"),
            created_at=updated_camera.get("created_at"),
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
