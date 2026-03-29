from fastapi import APIRouter

from app.api.v1.endpoints import auth, users, sensors, cameras, branches, groups, jobs, models, notifications

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(users.current_user_router, prefix="/user", tags=["users"])
api_router.include_router(sensors.router, prefix="/sensors", tags=["sensors"])
api_router.include_router(cameras.router, prefix="/cameras", tags=["cameras"])
api_router.include_router(branches.router, prefix="/branches", tags=["branches"])
api_router.include_router(groups.router, prefix="/groups", tags=["groups"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["Jobs"])
api_router.include_router(models.router, prefix="/models", tags=["Models"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
