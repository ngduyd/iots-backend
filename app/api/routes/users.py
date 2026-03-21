from fastapi import APIRouter, Depends, HTTPException

from app.schemas import ResponseMessage, UserCreateByAdminRequest, UserUpdateRequest
from app.security import get_current_user_record, require_admin
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
async def list_users(_admin: dict = Depends(require_admin)):
    users = await get_users_db()
    return ResponseMessage(
        code=200,
        message="Users retrieved successfully",
        data=users,
    )


@router.get("/{user_id}", response_model=ResponseMessage)
async def get_user(user_id: int, _admin: dict = Depends(require_admin)):
    row = await get_user_db(user_id)
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
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
    row = await create_user_db(
        username=user.username,
        password=user.password,
        group_id=admin_user.get("group_id"),
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
async def update_user(user_id: int, user: UserUpdateRequest, _admin: dict = Depends(require_admin)):
    row = await update_user_db(
        user_id=user_id,
        username=user.username,
        group_id=user.group_id,
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
async def delete_user(user_id: int, _admin: dict = Depends(require_admin)):
    deleted = await delete_user_db(user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")
    return ResponseMessage(
        code=200,
        message="User deleted successfully",
        data=None,
    )
