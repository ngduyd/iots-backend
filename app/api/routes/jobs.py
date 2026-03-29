import uuid
import secrets
from fastapi import APIRouter, Depends, HTTPException, Query
from app.schemas import (
    JobCreateRequest,
    JobUpdateRequest,
    JobResponse,
    ResponseMessage,
    DatasetParams,
    FeatureEngineeringParams,
    ForecastParams,
    ModelHyperparams,
)
from app.security import get_current_user_record, is_superadmin
from app.services.database import (
    create_job_db,
    get_job_db,
    update_job_status_db,
    cancel_job_db,
    get_branch as get_branch_db,
)

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])

@router.get("/defaults", response_model=ResponseMessage)
async def get_job_defaults():
    """
    Returns default parameters for job creation to simplify frontend form handling.
    """
    from datetime import timedelta, datetime as dt
    now = dt.now()
    defaults = {
        "dataset": {
            "branch_id": 1,
            "date_from": (now - timedelta(days=30)).isoformat(),
            "date_to": now.isoformat(),
            "features": ["co2", "temp", "rh", "people"],
            "targets": ["co2", "temp", "rh"]
        },
        "feature_engineering": {
            "lags": [1, 2, 3, 5, 10, 20],
            "rolls": [5, 10, 20],
            "use_time_features": True,
            "use_diff_features": True,
            "use_occupancy": True,
            "use_interaction": True
        },
        "forecast": {
            "horizon": 15,
            "step_ahead": 10
        },
        "model_hyperparams": {
            "n_estimators": 500,
            "max_depth": 6,
            "learning_rate": 0.03,
            "subsample": 0.8,
            "colsample_bytree": 0.8
        }
    }
    return ResponseMessage(code=200, message="Defaults retrieved", data=defaults)

@router.post("/create", response_model=ResponseMessage)
async def create_job(
    request: JobCreateRequest,
    current_user: dict = Depends(get_current_user_record),
):
    # Verify branch access
    branch = await get_branch_db(
        request.dataset.branch_id,
        None if is_superadmin(current_user) else current_user.get("group_id"),
    )
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found or access denied")

    job_id = str(uuid.uuid4())
    secret = secrets.token_urlsafe(32)

    job = await create_job_db(
        job_id=job_id,
        branch_id=request.dataset.branch_id,
        user_id=current_user["user_id"],
        secret=secret,
        dataset_params=request.dataset.dict(),
        feature_params=request.feature_engineering.dict(),
        forecast_params=request.forecast.dict(),
        model_params=request.model_hyperparams.dict(),
    )

    if not job:
        raise HTTPException(status_code=500, detail="Failed to create job in database")

    return ResponseMessage(
        code=201, 
        message="Job created successfully", 
        data={"job_id": job_id, "secret": secret}
    )

@router.get("/status/{job_id}", response_model=ResponseMessage)
async def get_job_status(
    job_id: str,
    current_user: dict = Depends(get_current_user_record),
):
    job = await get_job_db(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Verify access (Superadmin or same group as branch)
    branch = await get_branch_db(
        job["branch_id"],
        None if is_superadmin(current_user) else current_user.get("group_id"),
    )
    if not branch:
        raise HTTPException(status_code=403, detail="Access denied to this job's data")

    return ResponseMessage(code=200, message="Job details retrieved", data=dict(job))

@router.post("/cancel/{job_id}", response_model=ResponseMessage)
async def cancel_job(
    job_id: str,
    current_user: dict = Depends(get_current_user_record),
):
    job = await get_job_db(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Verify access
    branch = await get_branch_db(
        job["branch_id"],
        None if is_superadmin(current_user) else current_user.get("group_id"),
    )
    if not branch:
        raise HTTPException(status_code=403, detail="Access denied")

    if job["status"] in ["completed", "failed", "cancelled"]:
        raise HTTPException(status_code=400, detail=f"Cannot cancel job in status: {job['status']}")

    updated = await cancel_job_db(job_id)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to cancel job")

    return ResponseMessage(code=200, message="Job cancelled successfully", data=updated)

@router.post("/update/{job_id}", response_model=ResponseMessage)
async def update_job_server_to_server(
    job_id: str,
    update_data: JobUpdateRequest,
):
    """
    Endpoint for external AI Server to update status and results.
    Bypasses user JWT auth in favor of a per-job secret.
    """
    job = await get_job_db(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Verify Secret
    if secrets.compare_digest(job["secret"], update_data.secret) is False:
        raise HTTPException(status_code=401, detail="Invalid job secret")

    updated = await update_job_status_db(
        job_id=job_id,
        status=update_data.status,
        result=update_data.result
    )

    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update job status")

    return ResponseMessage(code=200, message="Job status updated by server", data=updated)
