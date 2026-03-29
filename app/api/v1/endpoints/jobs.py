import uuid
import secrets
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.encoders import jsonable_encoder

from app.schemas.job import JobCreateRequest, JobUpdateRequest
from app.schemas.common import ResponseMessage, PaginationQuery
from app.core import security
from app.services import job_service, branch_service

router = APIRouter()

@router.get("/defaults", response_model=ResponseMessage)
async def get_job_defaults():
    defaults = job_service.get_job_defaults_data()
    return ResponseMessage(code=200, message="Defaults retrieved", data=defaults)

@router.post("/create", response_model=ResponseMessage)
async def create_job(
    request: JobCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(security.get_current_user_record),
):
    branch = await branch_service.get_branch(
        request.dataset.branch_id,
        None if security.is_superadmin(current_user) else current_user.get("group_id"),
    )
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found or access denied")

    job_id = str(uuid.uuid4())
    secret = secrets.token_urlsafe(32)

    data_ok, reason = await job_service.job_repo.verify_job_data_exists(
        request.dataset.branch_id,
        request.dataset.features,
        request.dataset.date_from,
        request.dataset.date_to
    )

    status = "pending" if data_ok else "failed"
    message = None if data_ok else reason

    job = await job_service.job_repo.create_job(
        job_id=job_id,
        branch_id=request.dataset.branch_id,
        user_id=current_user["user_id"],
        secret=secret,
        dataset_params=jsonable_encoder(request.dataset),
        feature_params=jsonable_encoder(request.feature_engineering),
        forecast_params=jsonable_encoder(request.forecast),
        model_params=jsonable_encoder(request.model_hyperparams),
        status=status,
        message=message
    )

    if job and data_ok:
        background_tasks.add_task(
            job_service.process_and_notify_ai_server,
            job_id=job_id,
            secret=secret,
            branch_id=request.dataset.branch_id,
            date_from=request.dataset.date_from,
            date_to=request.dataset.date_to,
            request_payload=jsonable_encoder(request)
        )

    if not job:
        raise HTTPException(status_code=500, detail="Failed to create job in database")

    msg = "Job created successfully" if data_ok else f"Job created with failure: {reason}"
    return ResponseMessage(
        code=201, 
        message=msg, 
        data={"job_id": job_id, "status": status, "message": message}
    )

@router.get("/status/{job_id}", response_model=ResponseMessage)
async def get_job_status(
    job_id: str,
    current_user: dict = Depends(security.get_current_user_record),
):
    job = await job_service.job_repo.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    branch = await branch_service.get_branch(
        job["branch_id"],
        None if security.is_superadmin(current_user) else current_user.get("group_id"),
    )
    if not branch:
        raise HTTPException(status_code=403, detail="Access denied to this job's data")

    return ResponseMessage(code=200, message="Job details retrieved", data=dict(job))

@router.post("/cancel/{job_id}", response_model=ResponseMessage)
async def cancel_job(
    job_id: str,
    current_user: dict = Depends(security.get_current_user_record),
):
    job = await job_service.job_repo.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    branch = await branch_service.get_branch(
        job["branch_id"],
        None if security.is_superadmin(current_user) else current_user.get("group_id"),
    )
    if not branch:
        raise HTTPException(status_code=403, detail="Access denied")

    if job["status"] in ["completed", "failed", "cancelled"]:
        raise HTTPException(status_code=400, detail=f"Cannot cancel job in status: {job['status']}")

    updated = await job_service.job_repo.cancel_job(job_id)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to cancel job")

    return ResponseMessage(code=200, message="Job cancelled successfully", data=updated)

@router.post("/update/{job_id}", response_model=ResponseMessage)
async def update_job_server_to_server(
    job_id: str,
    update_data: JobUpdateRequest,
):
    job = await job_service.job_repo.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if secrets.compare_digest(job["secret"], update_data.secret) is False:
        raise HTTPException(status_code=401, detail="Invalid job secret")

    res_model_id = update_data.model_id
    if not res_model_id and update_data.result:
        res_model_id = update_data.result.get("model_id")
    
    if res_model_id:
        res_model_name = update_data.model_name or f"Model {str(res_model_id)[:8]}"
        branch = await branch_service.get_branch(job["branch_id"])
        if branch:
            await job_service.job_repo.get_or_create_model(
                group_id=branch["group_id"],
                model_id=res_model_id,
                name=res_model_name
            )

    updated = await job_service.job_repo.update_job_status(
        job_id=job_id,
        status=update_data.status,
        result=update_data.result,
        message=update_data.message,
        model_id=res_model_id
    )

    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update job status")

    return ResponseMessage(code=200, message="Job status updated by server", data=updated)

@router.get("", response_model=ResponseMessage)
async def get_jobs(
    status: str | None = Query(None, description="Filter by job status (pending, running, completed, failed, cancelled)"),
    query: PaginationQuery = Depends(),
    current_user: dict = Depends(security.get_current_user_record),
):
    jobs = await job_service.job_repo.get_jobs(
        group_id=None if security.is_superadmin(current_user) else current_user.get("group_id"),
        status=status,
        limit=query.limit
    )
    return ResponseMessage(code=200, message="Jobs retrieved", data=jobs)
