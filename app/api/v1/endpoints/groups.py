from fastapi import APIRouter, Depends, HTTPException

from app.schemas.group import GroupCreateRequest
from app.schemas.common import ResponseMessage
from app.core import security
from app.services import branch_service

router = APIRouter()

@router.get("", response_model=ResponseMessage)
async def list_groups(current_user: dict = Depends(security.get_current_user_record)):
	if security.is_superadmin(current_user):
		groups = await branch_service.get_groups()
	else:
		group_id = current_user.get("group_id")
		group = await branch_service.get_group(group_id) if group_id is not None else None
		groups = [group] if group else []

	return ResponseMessage(
		code=200,
		message="Groups retrieved successfully",
		data=groups,
	)

@router.get("/{group_id}", response_model=ResponseMessage)
async def get_group(group_id: int, current_user: dict = Depends(security.get_current_user_record)):
	if not security.is_superadmin(current_user) and current_user.get("group_id") != group_id:
		raise HTTPException(status_code=403, detail="Permission denied")

	row = await branch_service.get_group(group_id)
	if not row:
		raise HTTPException(status_code=404, detail="Group not found")

	return ResponseMessage(
		code=200,
		message="Group retrieved successfully",
		data=row,
	)

@router.post("", response_model=ResponseMessage)
async def create_group(group: GroupCreateRequest, admin_user: dict = Depends(security.require_admin)):
	if not security.is_superadmin(admin_user):
		raise HTTPException(status_code=403, detail="Only superadmin can create groups")

	row = await branch_service.create_group(name=group.name)
	if not row:
		raise HTTPException(status_code=400, detail="Cannot create group")

	return ResponseMessage(
		code=200,
		message="Group created successfully",
		data=row,
	)

@router.put("/{group_id}", response_model=ResponseMessage)
async def update_group(
	group_id: int,
	group: GroupCreateRequest,
	admin_user: dict = Depends(security.require_admin),
):
	if not security.is_superadmin(admin_user) and admin_user.get("group_id") != group_id:
		raise HTTPException(status_code=403, detail="Permission denied")

	row = await branch_service.update_group(group_id=group_id, name=group.name)
	if not row:
		raise HTTPException(status_code=404, detail="Group not found")

	return ResponseMessage(
		code=200,
		message="Group updated successfully",
		data=row,
	)

@router.delete("/{group_id}", response_model=ResponseMessage)
async def delete_group(group_id: int, admin_user: dict = Depends(security.require_admin)):
	if not security.is_superadmin(admin_user):
		raise HTTPException(status_code=403, detail="Only superadmin can delete groups")

	deleted = await branch_service.delete_group(group_id)
	if not deleted:
		raise HTTPException(status_code=404, detail="Group not found")

	return ResponseMessage(
		code=200,
		message="Group deleted successfully",
		data=None,
	)
