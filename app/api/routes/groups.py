from fastapi import APIRouter, Depends, HTTPException
from app.schemas import GroupCreateRequest, ResponseMessage
from app.security import get_current_user_record, is_superadmin, require_admin
from app.services.database import (
	create_group as create_group_db,
	create_log,
	delete_group as delete_group_db,
	get_group as get_group_db,
	get_groups as get_groups_db,
	update_group as update_group_db,
)

router = APIRouter(prefix="/api/groups", tags=["groups"])


@router.get("", response_model=ResponseMessage)
async def list_groups(current_user: dict = Depends(get_current_user_record)):
	if is_superadmin(current_user):
		groups = await get_groups_db()
	else:
		group_id = current_user.get("group_id")
		group = await get_group_db(group_id) if group_id is not None else None
		groups = [group] if group else []

	return ResponseMessage(
		code=200,
		message="Groups retrieved successfully",
		data=groups,
	)


@router.get("/{group_id}", response_model=ResponseMessage)
async def get_group(group_id: int, current_user: dict = Depends(get_current_user_record)):
	if not is_superadmin(current_user) and current_user.get("group_id") != group_id:
		raise HTTPException(status_code=403, detail="Permission denied")

	row = await get_group_db(group_id)
	if not row:
		raise HTTPException(status_code=404, detail="Group not found")

	return ResponseMessage(
		code=200,
		message="Group retrieved successfully",
		data=row,
	)


@router.post("", response_model=ResponseMessage)
async def create_group(group: GroupCreateRequest, admin_user: dict = Depends(require_admin)):
	if not is_superadmin(admin_user):
		raise HTTPException(status_code=403, detail="Only superadmin can create groups")

	row = await create_group_db(name=group.name)
	if not row:
		raise HTTPException(status_code=400, detail="Cannot create group")

	await create_log(
		user_id=admin_user["user_id"],
		action="CREATE_GROUP",
		group_id=None,  # Group creation is a global action
		target_type="group",
		target_id=str(row["group_id"]),
		details={"name": group.name}
	)

	return ResponseMessage(
		code=200,
		message="Group created successfully",
		data=row,
	)


@router.put("/{group_id}", response_model=ResponseMessage)
async def update_group(
	group_id: int,
	group: GroupCreateRequest,
	admin_user: dict = Depends(require_admin),
):
	if not is_superadmin(admin_user) and admin_user.get("group_id") != group_id:
		raise HTTPException(status_code=403, detail="Permission denied")

	row = await update_group_db(group_id=group_id, name=group.name)
	if not row:
		raise HTTPException(status_code=404, detail="Group not found")

	await create_log(
		user_id=admin_user["user_id"],
		action="UPDATE_GROUP",
		group_id=group_id,
		target_type="group",
		target_id=str(group_id),
		details={"name": group.name}
	)

	return ResponseMessage(
		code=200,
		message="Group updated successfully",
		data=row,
	)


@router.delete("/{group_id}", response_model=ResponseMessage)
async def delete_group(group_id: int, admin_user: dict = Depends(require_admin)):
	if not is_superadmin(admin_user):
		raise HTTPException(status_code=403, detail="Only superadmin can delete groups")

	deleted = await delete_group_db(group_id)
	if not deleted:
		raise HTTPException(status_code=404, detail="Group not found")

	await create_log(
		user_id=admin_user["user_id"],
		action="DELETE_GROUP",
		group_id=group_id,
		target_type="group",
		target_id=str(group_id)
	)

	return ResponseMessage(
		code=200,
		message="Group deleted successfully",
		data=None,
	)
