from fastapi import APIRouter, Depends, HTTPException

from app.schemas import BranchCreateByAdminRequest, BranchCreateRequest, BranchResponse, ResponseMessage
from app.security import get_current_user, require_admin
from app.services.database import (
    create_branch as create_branch_db,
    delete_branch as delete_branch_db,
    get_branch as get_branch_db,
    get_branches as get_branches_db,
    update_branch as update_branch_db,
)

router = APIRouter(prefix="/api/branches", tags=["branches"])


@router.get("", response_model=ResponseMessage)
async def list_branches(_user: str = Depends(get_current_user)):
    branches = await get_branches_db()
    return ResponseMessage(
        code=200,
        message="Branches retrieved successfully",
        data=branches
    )


@router.get("/{branch_id}", response_model=ResponseMessage)
async def get_branch(branch_id: int, _user: str = Depends(get_current_user)):
    row = await get_branch_db(branch_id)
    if not row:
        raise HTTPException(status_code=404, detail="Branch not found")
    return ResponseMessage(
        code=200,
        message="Branch retrieved successfully",
        data=row
    )


@router.post("", response_model=ResponseMessage)
async def create_branch(
    branch: BranchCreateByAdminRequest,
    admin_user: dict = Depends(require_admin),
):
    row = await create_branch_db(
        group_id=admin_user.get("group_id"),
        name=branch.name,
        alert=branch.alert,
    )
    if not row:
        raise HTTPException(status_code=400, detail="Cannot create branch")
    return ResponseMessage(
        code=200,
        message="Branch created successfully",
        data=row
    )


@router.put("/{branch_id}", response_model=ResponseMessage)
async def update_branch(branch_id: int, branch: BranchCreateRequest, _user: str = Depends(get_current_user)):
    row = await update_branch_db(
        branch_id=branch_id,
        group_id=branch.group_id,
        name=branch.name,
        alert=branch.alert,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Branch not found")
    return ResponseMessage(
        code=200,
        message="Branch updated successfully",
        data=row
    )


@router.delete("/{branch_id}", response_model=ResponseMessage)
async def delete_branch(branch_id: int, _user: str = Depends(get_current_user)):
    deleted = await delete_branch_db(branch_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Branch not found")
    return ResponseMessage(
        code=200,
        message="Branch deleted successfully",
        data=None
    )