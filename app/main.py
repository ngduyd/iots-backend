from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from app.api.v1.api import api_router as api_v1_router
from app.core import config
from app.workers.runtime import runtime
from app.db.session import close_db
from app.db.init_db import init_db, ensure_default_admin_user
from app.repositories.camera_repo import reset_all_cameras_offline

@asynccontextmanager
async def lifespan(_app: FastAPI):
    print("[INIT] Initializing database...")
    try:
        await init_db()
        admin_ready = await ensure_default_admin_user()
        if admin_ready:
            print("[INIT] Default admin and superadmin users are ready")
        else:
            print("[INIT] Warning: Could not ensure default admin/superadmin users")
    except Exception as e:
        print(f"[INIT] Database initialization failed: {e}")

    # Ensure all cameras are marked offline on startup
    await reset_all_cameras_offline()

    # Start the background MQTT and camera analysis runtime
    await runtime.start()
    
    try:
        yield
    finally:
        # Graceful shutdown
        await runtime.stop()
        await close_db()

app = FastAPI(
    title="IoT Backend API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Session middleware for authentication
app.add_middleware(
    SessionMiddleware,
    secret_key=config.SESSION_SECRET,
    max_age=config.SESSION_MAX_AGE_SECONDS,
    same_site="lax",
    https_only=False,
)

# Mount versioned API routes
app.include_router(api_v1_router, prefix="/api/v1")

# Mount legacy prefix for backward compatibility
app.include_router(api_v1_router, prefix="/api")

@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}
