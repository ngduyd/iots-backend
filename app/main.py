from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from app.api.routes.auth import router as auth_router
from app.api.routes.branches import router as branches_router
from app.api.routes.groups import router as groups_router
from app.api.routes.sensors import router as sensors_router
from app.api.routes.users import current_user_router, router as users_router
from app.core import config
from app.runtime import MqttRuntime
from app.services import manager
from app.services.database import close_db, ensure_default_admin_user, init_db

runtime = MqttRuntime()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    print("Initializing database...")
    try:
        await init_db()
        admin_user = await ensure_default_admin_user()
        if admin_user is not None:
            print("Default admin user is ready")
        else:
            print("Cannot ensure default admin user")
    except Exception as e:
        print(f"Database initialization failed: {e}")

    print("Initializing sensor manager...")
    try:
        await manager.init()
    except Exception as e:
        print(f"Sensor manager initialization failed: {e}")

    await runtime.start()
    try:
        yield
    finally:
        await runtime.stop()
        await close_db()


app = FastAPI(
    title="MQTT Backend API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)
app.add_middleware(
    SessionMiddleware,
    secret_key=config.SESSION_SECRET,
    max_age=config.SESSION_MAX_AGE_SECONDS,
    same_site="lax",
    https_only=False,
)
app.include_router(auth_router)
app.include_router(groups_router)
app.include_router(sensors_router)
app.include_router(branches_router)
app.include_router(current_user_router)
app.include_router(users_router)
