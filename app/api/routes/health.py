from fastapi import APIRouter

from app.schemas import HealthResponse

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check():
    from app.main import runtime

    return HealthResponse(mqtt_running=runtime.running, db_ready=runtime.db_ready)
