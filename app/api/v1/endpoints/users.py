from fastapi import APIRouter, Depends, HTTPException

from app.schemas.user import UserCreateByAdminRequest, UserUpdateRequest
from app.schemas.common import ResponseMessage
from app.core import security
from app.services import user_service

router = APIRouter()
current_user_router = APIRouter()

@current_user_router.get("", response_model=ResponseMessage)
async def get_current_user_profile(current_user: dict = Depends(security.get_current_user_record)):
    return ResponseMessage(
        code=200,
        message="Current user retrieved successfully",
        data=current_user,
    )

@router.get("", response_model=ResponseMessage)
async def list_users(admin_user: dict = Depends(security.require_admin)):
    if not security.is_superadmin(admin_user) and admin_user.get("group_id") is None:
        raise HTTPException(status_code=403, detail="Admin user is not assigned to any group")

    if security.is_superadmin(admin_user):
        users = await user_service.get_users()
    else:
        users = await user_service.get_users(group_id=admin_user.get("group_id"))

    return ResponseMessage(
        code=200,
        message="Users retrieved successfully",
        data=users,
    )

@router.get("/{user_id}", response_model=ResponseMessage)
async def get_user(user_id: int, admin_user: dict = Depends(security.require_admin)):
    row = await user_service.get_user(user_id)
    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    if not security.is_superadmin(admin_user) and row.get("group_id") != admin_user.get("group_id"):
        raise HTTPException(status_code=403, detail="Permission denied")

    return ResponseMessage(
        code=200,
        message="User retrieved successfully",
        data=row,
    )

@router.post("", response_model=ResponseMessage)
async def create_user(
    user: UserCreateByAdminRequest,
    admin_user: dict = Depends(security.require_admin),
):
    if not security.is_superadmin(admin_user) and admin_user.get("group_id") is None:
        raise HTTPException(status_code=403, detail="Admin user is not assigned to any group")

    if not security.is_superadmin(admin_user) and user.role == "superadmin":
        raise HTTPException(status_code=403, detail="Permission denied")

    if security.is_superadmin(admin_user) and user.group_id is None:
        raise HTTPException(status_code=400, detail="group_id is required for superadmin")

    existing_user = await user_service.get_user_by_username(user.username)
    if existing_user:
        raise HTTPException(status_code=409, detail="Username already exists")

    group_id = user.group_id if security.is_superadmin(admin_user) else admin_user.get("group_id")
    row = await user_service.create_user(
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
    current_user: dict = Depends(security.get_current_user_record),
):
    is_self = user_id == current_user.get("user_id")
    is_admin_or_super = current_user.get("role") in {"admin", "superadmin"}
    
    if not is_self and not is_admin_or_super:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    existing = await user_service.get_user(user_id)
    if not existing:
        raise HTTPException(status_code=404, detail="User not found")

    if security.is_superadmin(current_user):
        target_group_id = user.group_id if user.group_id is not None else existing["group_id"]
        target_role = user.role if user.role is not None else existing["role"]
    elif is_self:
        target_group_id = existing["group_id"]
        target_role = existing["role"]
    else:
        if existing.get("group_id") != current_user.get("group_id"):
            raise HTTPException(status_code=403, detail="Permission denied")
        
        target_role = user.role if user.role is not None else existing["role"]
        if target_role == "superadmin":
            raise HTTPException(status_code=403, detail="Permission denied")
        target_group_id = current_user.get("group_id")

    if user.username and user.username != existing["username"]:
        if await user_service.get_user_by_username(user.username):
            raise HTTPException(status_code=409, detail="Username already exists")

    row = await user_service.update_user(
        user_id=user_id,
        username=user.username,
        group_id=target_group_id,
        role=target_role,
        password=user.password,
    )
    if not row:
        raise HTTPException(status_code=400, detail="Update failed")

    return ResponseMessage(
        code=200,
        message="User updated successfully",
        data=row,
    )

@router.delete("/{user_id}", response_model=ResponseMessage)
async def delete_user(user_id: int, admin_user: dict = Depends(security.require_admin)):
    if not security.is_superadmin(admin_user) and admin_user.get("group_id") is None:
        raise HTTPException(status_code=403, detail="Admin user is not assigned to any group")

    existing = await user_service.get_user(user_id)
    if not existing:
        raise HTTPException(status_code=404, detail="User not found")

    if not security.is_superadmin(admin_user):
        if existing.get("group_id") != admin_user.get("group_id"):
            raise HTTPException(status_code=403, detail="Permission denied")
        if existing.get("role") == "superadmin":
            raise HTTPException(status_code=403, detail="Permission denied")

    deleted = await user_service.delete_user(user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")
    return ResponseMessage(
        code=200,
        message="User deleted successfully",
        data=None,
    )
