from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from app.schemas import LogListResponse, LogResponse, ResponseMessage
from app.security import get_current_user_record, is_superadmin, require_admin
from app.services.database import get_logs

router = APIRouter(prefix="/api/logs", tags=["logs"])

@router.get("", response_model=ResponseMessage)
async def list_logs(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    action: str | None = Query(None),
    target_type: str | None = Query(None),
    from_date: datetime | None = Query(None),
    to_date: datetime | None = Query(None),
    admin_user: dict = Depends(require_admin),
):
    """
    List system logs.
    Admins can only see logs for their group.
    Superadmins can see all logs.
    """
    group_id = None if is_superadmin(admin_user) else admin_user.get("group_id")
    
    if not is_superadmin(admin_user) and group_id is None:
        raise HTTPException(status_code=403, detail="Admin user is not assigned to any group")

    rows = await get_logs(
        limit=limit,
        offset=offset,
        group_id=group_id,
        action=action,
        target_type=target_type,
        from_date=from_date,
        to_date=to_date
    )
    
    items = [
        f"{row['created_at'].isoformat()} | {row['action']} | {row['message']}"
        for row in rows
    ]
    
    return ResponseMessage(
        code=200,
        message="Logs retrieved successfully",
        data=LogListResponse(count=len(items), items=items)
    )
