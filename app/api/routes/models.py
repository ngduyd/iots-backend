from fastapi import APIRouter, Depends, HTTPException
from app.schemas import ResponseMessage, ModelListResponse, ModelUpdateRequest, ModelResponse
from app.security import require_admin, is_superadmin
from app.services.database import get_models_db, update_model_name_db, delete_model_db

router = APIRouter(prefix="/api/models", tags=["Models"])

@router.get("", response_model=ResponseMessage)
async def list_models(current_user: dict = Depends(require_admin)):
    if is_superadmin(current_user):
        raise HTTPException(status_code=403, detail="Superadmins are not involved with models")
    
    group_id = current_user.get("group_id")
    if group_id is None:
        return ResponseMessage(code=200, message="Models retrieved", data=ModelListResponse(count=0, items=[]))
    
    models = await get_models_db(group_id)
    formatted_models = []
    for m in models:
        m_dict = dict(m)
        m_dict["model_id"] = str(m_dict["model_id"])
        formatted_models.append(m_dict)
        
    return ResponseMessage(
        code=200, 
        message="Models retrieved", 
        data=ModelListResponse(count=len(formatted_models), items=formatted_models)
    )

@router.patch("/{model_id}", response_model=ResponseMessage)
async def update_model_name(
    model_id: str,
    request: ModelUpdateRequest,
    current_user: dict = Depends(require_admin)
):
    if is_superadmin(current_user):
        raise HTTPException(status_code=403, detail="Superadmins are not involved with models")
        
    group_id = current_user.get("group_id")
    if group_id is None:
        raise HTTPException(status_code=400, detail="Admin does not belong to a group")
        
    updated = await update_model_name_db(model_id, request.name, group_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Model not found or access denied")
        
    res = dict(updated)
    res["model_id"] = str(res["model_id"])
    
    return ResponseMessage(code=200, message="Model name updated", data=res)

@router.delete("/{model_id}", response_model=ResponseMessage)
async def delete_model(
    model_id: str,
    current_user: dict = Depends(require_admin)
):
    if is_superadmin(current_user):
        raise HTTPException(status_code=403, detail="Superadmins are not involved with models")
        
    group_id = current_user.get("group_id")
    if group_id is None:
        raise HTTPException(status_code=400, detail="Admin does not belong to a group")
        
    deleted = await delete_model_db(model_id, group_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Model not found or access denied")
        
    res = dict(deleted)
    res["model_id"] = str(res["model_id"])
    
    return ResponseMessage(code=200, message="Model deleted (soft delete)", data=res)
