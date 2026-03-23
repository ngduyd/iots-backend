from fastapi import APIRouter, Depends, HTTPException

from app.schemas import ResponseMessage, UserCreateByAdminRequest, UserUpdateRequest
from app.security import get_current_user_record, is_superadmin, require_admin
from app.services.database import (
    create_user as create_user_db,
    delete_user as delete_user_db,
    get_user as get_user_db,
    get_users as get_users_db,
    update_user as update_user_db,
)

router = APIRouter(prefix="/api/users", tags=["users"])
current_user_router = APIRouter(prefix="/api/user", tags=["users"])


@current_user_router.get("", response_model=ResponseMessage)
async def get_current_user_profile(current_user: dict = Depends(get_current_user_record)):
    row = current_user
    if not row:
        raise HTTPException(status_code=404, detail="Current user not found")
    return ResponseMessage(
        code=200,
        message="Current user retrieved successfully",
        data=row,
    )


@router.get("", response_model=ResponseMessage)
async def list_users(admin_user: dict = Depends(require_admin)):
    if not is_superadmin(admin_user) and admin_user.get("group_id") is None:
        raise HTTPException(status_code=403, detail="Admin user is not assigned to any group")

    if is_superadmin(admin_user):
        users = await get_users_db()
    else:
        users = await get_users_db(group_id=admin_user.get("group_id"))

    return ResponseMessage(
        code=200,
        message="Users retrieved successfully",
        data=users,
    )


@router.get("/{user_id}", response_model=ResponseMessage)
async def get_user(user_id: int, admin_user: dict = Depends(require_admin)):
    row = await get_user_db(user_id)
    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    if not is_superadmin(admin_user) and row.get("group_id") != admin_user.get("group_id"):
        raise HTTPException(status_code=403, detail="Permission denied")

    return ResponseMessage(
        code=200,
        message="User retrieved successfully",
        data=row,
    )


@router.post("", response_model=ResponseMessage)
async def create_user(
    user: UserCreateByAdminRequest,
    admin_user: dict = Depends(require_admin),
):
    if not is_superadmin(admin_user) and admin_user.get("group_id") is None:
        raise HTTPException(status_code=403, detail="Admin user is not assigned to any group")

    if not is_superadmin(admin_user) and user.role == "superadmin":
        raise HTTPException(status_code=403, detail="Permission denied")

    if is_superadmin(admin_user) and user.group_id is None:
        raise HTTPException(status_code=400, detail="group_id is required for superadmin")

    group_id = user.group_id if is_superadmin(admin_user) else admin_user.get("group_id")
    row = await create_user_db(
        username=user.username,
        password=user.password,
        group_id=group_id,
        role=user.role,
    )
    if not row:
        raise HTTPException(status_code=400, detail="Cannot create user")
    return ResponseMessage(
        code=200,
        message="User created successfully",
        data=row,
    )


@router.put("/{user_id}", response_model=ResponseMessage)
async def update_user(
    user_id: int,
    user: UserUpdateRequest,
    admin_user: dict = Depends(require_admin),
):
    if not is_superadmin(admin_user) and admin_user.get("group_id") is None:
        raise HTTPException(status_code=403, detail="Admin user is not assigned to any group")

    existing = await get_user_db(user_id)
    if not existing:
        raise HTTPException(status_code=404, detail="User not found")

    if not is_superadmin(admin_user):
        if existing.get("group_id") != admin_user.get("group_id"):
            raise HTTPException(status_code=403, detail="Permission denied")
        if user.group_id not in (None, admin_user.get("group_id")):
            raise HTTPException(status_code=403, detail="Permission denied")
        if user.role == "superadmin":
            raise HTTPException(status_code=403, detail="Permission denied")

    row = await update_user_db(
        user_id=user_id,
        username=user.username,
        group_id=user.group_id if is_superadmin(admin_user) else admin_user.get("group_id"),
        role=user.role,
    )
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return ResponseMessage(
        code=200,
        message="User updated successfully",
        data=row,
    )


@router.delete("/{user_id}", response_model=ResponseMessage)
async def delete_user(user_id: int, admin_user: dict = Depends(require_admin)):
    if not is_superadmin(admin_user) and admin_user.get("group_id") is None:
        raise HTTPException(status_code=403, detail="Admin user is not assigned to any group")

    existing = await get_user_db(user_id)
    if not existing:
        raise HTTPException(status_code=404, detail="User not found")

    if not is_superadmin(admin_user):
        if existing.get("group_id") != admin_user.get("group_id"):
            raise HTTPException(status_code=403, detail="Permission denied")
        if existing.get("role") == "superadmin":
            raise HTTPException(status_code=403, detail="Permission denied")

    deleted = await delete_user_db(user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")
    return ResponseMessage(
        code=200,
        message="User deleted successfully",
        data=None,
    )
