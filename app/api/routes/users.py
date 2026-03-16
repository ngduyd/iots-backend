from fastapi import APIRouter, Depends, HTTPException

from app.schemas import ResponseMessage, UserCreateRequest, UserUpdateRequest
from app.security import get_current_user
from app.services.database import (
    create_user as create_user_db,
    delete_user as delete_user_db,
    get_user as get_user_db,
    get_users as get_users_db,
    update_user as update_user_db,
)

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=ResponseMessage)
async def list_users(_user: str = Depends(get_current_user)):
    users = await get_users_db()
    return ResponseMessage(
        code=200,
        message="Users retrieved successfully",
        data=users,
    )


@router.get("/{user_id}", response_model=ResponseMessage)
async def get_user(user_id: int, _user: str = Depends(get_current_user)):
    row = await get_user_db(user_id)
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return ResponseMessage(
        code=200,
        message="User retrieved successfully",
        data=row,
    )


@router.post("", response_model=ResponseMessage)
async def create_user(user: UserCreateRequest, _user: str = Depends(get_current_user)):
    row = await create_user_db(
        username=user.username,
        password=user.password,
        group_id=user.group_id,
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
async def update_user(user_id: int, user: UserUpdateRequest, _user: str = Depends(get_current_user)):
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
async def delete_user(user_id: int, _user: str = Depends(get_current_user)):
    deleted = await delete_user_db(user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")
    return ResponseMessage(
        code=200,
        message="User deleted successfully",
        data=None,
    )
