from fastapi import APIRouter, Depends, HTTPException

from app.schemas import GroupCreateRequest, GroupResponse, ResponseMessage
from app.security import get_current_user
from app.services.database import (
	create_group as create_group_db,
	delete_group as delete_group_db,
	get_group as get_group_db,
	get_groups as get_groups_db,
	update_group as update_group_db,
)

router = APIRouter(prefix="/api/groups", tags=["groups"])


@router.get("", response_model=ResponseMessage)
async def list_groups(_user: str = Depends(get_current_user)):
	groups = await get_groups_db()
	return ResponseMessage(
		code=200,
		message="Groups retrieved successfully",
		data=groups
	)


@router.get("/{group_id}", response_model=ResponseMessage)
async def get_group(group_id: int, _user: str = Depends(get_current_user)):
	row = await get_group_db(group_id)
	if not row:
		raise HTTPException(status_code=404, detail="Group not found")
	return ResponseMessage(
		code=200,
		message="Group retrieved successfully",
		data=row
	)


@router.post("", response_model=ResponseMessage)
async def create_group(group: GroupCreateRequest, _user: str = Depends(get_current_user)):
	row = await create_group_db(name=group.name)
	if not row:
		raise HTTPException(status_code=400, detail="Cannot create group")
	return ResponseMessage(
		code=200,
		message="Group created successfully",
		data=row
	)


@router.put("/{group_id}", response_model=ResponseMessage)
async def update_group(group_id: int, group: GroupCreateRequest, _user: str = Depends(get_current_user)):
	row = await update_group_db(group_id=group_id, name=group.name)
	if not row:
		raise HTTPException(status_code=404, detail="Group not found")
	return ResponseMessage(
		code=200,
		message="Group updated successfully",
		data=row
	)


@router.delete("/{group_id}", response_model=ResponseMessage)
async def delete_group(group_id: int, _user: str = Depends(get_current_user)):
	deleted = await delete_group_db(group_id)
	if not deleted:
		raise HTTPException(status_code=404, detail="Group not found")
	return ResponseMessage(
		code=200,
		message="Group deleted successfully",
		data=None
	)
