# MQTT Backend Service

Python backend service that ingests MQTT sensor messages, stores data in PostgreSQL, and exposes authenticated HTTP APIs using FastAPI.

## Architecture

- `app/main.py`: FastAPI app, middleware, and router registration.
- `app/runtime.py`: startup/shutdown runtime (database, MQTT, manager).
- `app/api/routes/`: API modules (`auth`, `users`, `groups`, `branches`, `sensors`).
- `app/security.py`: session handling and permission helpers.
- `app/services/database.py`: async PostgreSQL queries and schema bootstrap.
- `app/services/mqtt_client.py`: MQTT client integration.
- `app/services/manager.py`: sensor online/offline management.
- `app/core/config.py`: environment variable loading.
- `main.py`: local launcher for Uvicorn.

## Tech Stack

- FastAPI
- asyncpg (PostgreSQL)
- paho-mqtt
- Uvicorn

## Auth and Roles

- Session-based auth via cookies (`sid` + Starlette session).
- Roles: `user`, `admin`, `superadmin`.
- Default bootstrap accounts are ensured at startup:
  - `superadmin` / `superadmin123`
  - `admin` / `admin123`

## Soft Delete for Sensors

- Sensors are soft-deleted using `deleted_at`.
- Soft delete endpoint sets `deleted_at = NOW()`.
- Read queries only return active sensors (`deleted_at IS NULL`).

## API Endpoints

### Auth

- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/validate`

### Current User

- `GET /api/user`

### Users

- `GET /api/users`
- `GET /api/users/{user_id}`
- `POST /api/users`
- `PUT /api/users/{user_id}`
- `DELETE /api/users/{user_id}`

### Groups

- `GET /api/groups`
- `GET /api/groups/{group_id}`
- `POST /api/groups`
- `PUT /api/groups/{group_id}`
- `DELETE /api/groups/{group_id}`

### Branches

- `GET /api/branches`
- `GET /api/branches/{branch_id}`
- `GET /api/branches/{branch_id}/sensors`
- `POST /api/branches`
- `PUT /api/branches/{branch_id}`
- `DELETE /api/branches/{branch_id}`

### Sensors

- `GET /api/sensors`
- `GET /api/sensors/{sensor_id}`
- `GET /api/sensors/{sensor_id}/values`
- `POST /api/sensors`
- `PUT /api/sensors/{sensor_id}`
- `DELETE /api/sensors/{sensor_id}` (soft delete)

### Cameras

- `POST /api/cameras/verify-stream` (public, verifies `id` + `secret`)
- `GET /api/cameras`
- `GET /api/cameras/{camera_id}`
- `POST /api/cameras` (admin)
- `PUT /api/cameras/{camera_id}` (admin)
- `POST /api/cameras/{camera_id}/reset-secret` (admin)
- `DELETE /api/cameras/{camera_id}` (admin)

## Environment Variables

### MQTT

- `MQTT_BROKER`
- `MQTT_PORT` (default: `1883`)
- `MQTT_TOPIC` (default: `#`)
- `MQTT_USERNAME`
- `MQTT_PASSWORD`

### Database

- `DB_HOST` (default: `localhost`)
- `DB_PORT` (default: `5432`)
- `DB_NAME` (default: `sensors_db`)
- `DB_USER` (default: `user`)
- `DB_PASSWORD` (default: `password`)

### HTTP API

- `HTTP_HOST` (default: `0.0.0.0`)
- `HTTP_PORT` (default: `8000`)

### Auth

- `AUTH_USERNAME` (default: `admin`)
- `AUTH_PASSWORD` (default: `admin123`)
- `SESSION_SECRET` (default: `change-me-in-production`)
- `SESSION_MAX_AGE_SECONDS` (default: `3600`)

### Runtime

- `SENSOR_OFFLINE_TIMEOUT` (default: `120`)

## Run Locally (Windows PowerShell)

1. Create and activate venv:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Configure environment in `.env`.

4. Start app:

```powershell
python main.py
```

API default URL: `http://localhost:8000`
Docs: `http://localhost:8000/docs`

## Run with Docker Compose

```powershell
docker-compose up --build
```

- Backend API: `http://localhost:8000`
- MQTT broker: `localhost:1883`
- PostgreSQL debug port: `localhost:5433`

## Production Notes

- Change `AUTH_PASSWORD` and `SESSION_SECRET`.
- Run behind reverse proxy + TLS.
- Add migration tooling for schema evolution.
- Add test coverage for auth, role checks, and soft-delete behavior.
