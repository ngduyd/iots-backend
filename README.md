# MQTT Backend Service

Backend Python service that ingests sensor messages from MQTT, stores data in PostgreSQL, and exposes authenticated HTTP APIs.

## Architecture

The repository is remapped to a backend-friendly structure:

- `app/main.py`: FastAPI application entrypoint.
- `app/runtime.py`: runtime that boots database + MQTT consumer in app lifecycle.
- `app/api/routes/`: HTTP route modules (`health`, `auth`, `sensors`).
- `app/security.py`: session auth and route protection.
- `app/services/`: business/data services (`db`, `mqtt_client`, `manager`).
- `app/core/config.py`: environment config for MQTT, DB, HTTP, and auth.

Compatibility wrappers are kept at root (`main.py`, `db.py`, `config.py`, `manager.py`, `mqtt_client.py`) so old imports do not break immediately.

## Features

- MQTT consumer via `paho-mqtt`
- PostgreSQL persistence via `psycopg2`
- HTTP API via FastAPI
- Session-based authentication for protected routes
- Sensor online/offline tracking

## API Endpoints

- `GET /api/health`: service health (no auth)
- `POST /api/auth/login`: create session cookie
- `POST /api/auth/logout`: clear session cookie
- `GET /api/sensors`: list sensors (auth required)
- `GET /api/sensors/{sensor_name}/values`: list sensor values (auth required)

### Login Request Example

```json
{
  "username": "admin",
  "password": "admin123"
}
```

### Session Usage

- Login with `POST /api/auth/login`
- Browser or HTTP client stores session cookie automatically
- Call protected endpoints using the same cookie jar/session
- Logout with `POST /api/auth/logout`

## Environment Variables

### MQTT

- `MQTT_BROKER`
- `MQTT_PORT` (default: `1883`)
- `MQTT_TOPIC` (default: `#`)
- `MQTT_USERNAME`
- `MQTT_PASSWORD`

### Database

- `DB_HOST`
- `DB_PORT` (default: `5432`)
- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`

### HTTP API

- `HTTP_HOST` (default: `0.0.0.0`)
- `HTTP_PORT` (default: `8000`)

### Auth

- `AUTH_USERNAME` (default: `admin`)
- `AUTH_PASSWORD` (default: `admin123`)
- `SESSION_SECRET` (required in production)
- `SESSION_MAX_AGE_SECONDS` (default: `3600`)

### Runtime

- `SENSOR_OFFLINE_TIMEOUT` (default: `120`)

## Run Locally

1. Create and activate venv (PowerShell):

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Configure environment (copy `.env.example` to `.env` and update values).

4. Start backend:

```powershell
python main.py
```

Service will run on `http://localhost:8000` by default.

## Run with Docker Compose

```powershell
docker-compose up --build
```

- Backend API: `http://localhost:8000`
- MQTT broker: `localhost:1883`
- PostgreSQL debug port: `localhost:5433`

## Notes for Production

- Change `AUTH_PASSWORD` and `SESSION_SECRET`.
- Restrict API exposure with reverse proxy and TLS.
- Add proper logging, tests, and migration tooling.
