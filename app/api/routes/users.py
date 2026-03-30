from fastapi import APIRouter, Depends, HTTPException
from app.schemas import ResponseMessage, UserCreateByAdminRequest, UserUpdateRequest
from app.security import get_current_user_record, is_superadmin, require_admin
from app.services.database import (
    create_user as create_user_db,
    create_log,
    delete_user as delete_user_db,
    get_user as get_user_db,
    get_user_by_username as get_user_by_username_db,
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

    existing_user = await get_user_by_username_db(user.username)
    if existing_user:
        raise HTTPException(status_code=409, detail="Username already exists")

    group_id = user.group_id if is_superadmin(admin_user) else admin_user.get("group_id")
    row = await create_user_db(
        username=user.username,
        password=user.password,
        group_id=group_id,
        role=user.role,
    )
    if not row:
        raise HTTPException(status_code=400, detail="Cannot create user")
    
    await create_log(
        user_id=admin_user["user_id"],
        action="CREATE_USER",
        group_id=group_id,
        target_type="user",
        target_id=str(row["user_id"]),
        details={"username": user.username, "role": user.role}
    )

    return ResponseMessage(
        code=200,
        message="User created successfully",
        data=row,
    )


@router.put("/{user_id}", response_model=ResponseMessage)
async def update_user(
    user_id: int,
    user: UserUpdateRequest,
    current_user: dict = Depends(get_current_user_record),
):
    is_self = user_id == current_user.get("user_id")
    is_admin_or_super = current_user.get("role") in {"admin", "superadmin"}
    
    if not is_self and not is_admin_or_super:
        raise HTTPException(status_code=403, detail="Permission denied")
    existing = await get_user_db(user_id)
    if not existing:
        raise HTTPException(status_code=404, detail="User not found")

    if is_superadmin(current_user):
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
        if await get_user_by_username_db(user.username):
            raise HTTPException(status_code=409, detail="Username already exists")

    row = await update_user_db(
        user_id=user_id,
        username=user.username if user.username else existing["username"],
        group_id=target_group_id,
        role=target_role,
        password=user.password,
    )
    if not row:
        raise HTTPException(status_code=400, detail="Update failed")

    await create_log(
        user_id=current_user["user_id"],
        action="UPDATE_USER",
        group_id=target_group_id,
        target_type="user",
        target_id=str(user_id),
        details={"username": row["username"], "role": target_role}
    )

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

    await create_log(
        user_id=admin_user["user_id"],
        action="DELETE_USER",
        group_id=existing.get("group_id"),
        target_type="user",
        target_id=str(user_id),
        details={"username": existing.get("username")}
    )

    return ResponseMessage(
        code=200,
        message="User deleted successfully",
        data=None,
    )
