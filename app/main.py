from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from app.api.routes.auth import router as auth_router
from app.api.routes.health import router as health_router
from app.api.routes.sensors import router as sensors_router
from app.core import config
from app.runtime import MqttRuntime

runtime = MqttRuntime()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await runtime.start()
    yield
    await runtime.stop()


app = FastAPI(title="MQTT Backend API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=config.SESSION_SECRET,
    max_age=config.SESSION_MAX_AGE_SECONDS,
    same_site="lax",
    https_only=False,
)
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(sensors_router)
