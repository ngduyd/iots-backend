# MQTT Service

This Python application acts as a bridge between an MQTT broker and a PostgreSQL database. It listens to MQTT messages, extracts sensor data, and stores the readings in the `values` table so they can be consumed by dashboards, analytics jobs, or downstream services.

## Core Components
- `main.py`: Boots the service, connects to the MQTT broker, and starts the main loop.
- `mqtt_client.py`: Configures the Paho MQTT client and handles incoming messages.
- `db.py`: Creates the database schema and persists MQTT payloads to PostgreSQL.
- `config.py`: Reads MQTT/PostgreSQL settings from environment variables.
- `docker-compose.yaml`: Spins up the Python service alongside Mosquitto and PostgreSQL.
- `mosquitto/config/`: Bundled configuration for securing the broker (`mosquitto.conf`, `passwd`).

## Requirements
- Docker & Docker Compose (recommended for reproducible environments); or
- Python >= 3.12, `pip`, PostgreSQL, and Mosquitto for manual execution.

## Configuration Setup
1. Create an `.env` file from the template: `cp .env.example .env`.
2. Adjust the variables to match your environment (see the table below).
3. If you run the app outside Docker and want to load `.env`, uncomment `load_dotenv()` in `config.py`.

### Environment Variables
| Variable | Description | Default (docker-compose) |
| --- | --- | --- |
| `MQTT_BROKER` | MQTT broker host or IP | `mqtt`
| `MQTT_PORT` | MQTT port | `1883`
| `MQTT_TOPIC` | Topic to subscribe to | `sensors/data`
| `MQTT_USERNAME` | MQTT username (if required) | `user`
| `MQTT_PASSWORD` | MQTT password | `password`
| `DB_HOST` | PostgreSQL host | `database`
| `DB_PORT` | PostgreSQL port | `5432`
| `DB_NAME` | Database name | `mydb`
| `DB_USER` | Database user | `user`
| `DB_PASSWORD` | Database password | `password`

> `save_message` currently expects MQTT payloads in the form `"<type> <value>"` (e.g. `"temperature 27.5"`). Make sure your publishers follow this format.

## Run with Docker Compose
```bash
docker-compose up --build
```

- The Python service waits 5 seconds before connecting so PostgreSQL and Mosquitto have time to start.
- Mosquitto reads configuration and credentials from `./mosquitto/config`.
- PostgreSQL mounts the `db_data` Docker volume for persistent storage.
- Port `1883` is exposed on the host for MQTT publishers; PostgreSQL is reachable on `5433` for debugging.

## Run Manually (without Docker)
1. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
2. Make sure Mosquitto and PostgreSQL are running and environment variables are exported (or enable `load_dotenv()` in `config.py`).
3. Start the service:
   ```bash
   python main.py
   ```

## Database Schema
`db.init_db()` creates two tables:
- `sensors`: catalog of sensor topics with an auto-increment primary key.
- `values`: stores every measurement, links to `sensors.sensor_id`, and records the payload type, numeric value, and timestamp.

Indexes `idx_type_time` and `idx_sensor_value` make querying by data type or sensor efficient.

## Development Ideas
- Add automated tests for `db.save_message` to validate payload parsing.
- Extend the payload format (e.g. JSON) so you can capture metadata such as `unit` or `device_id`.
- Consider adding health checks and structured logging (e.g. `structlog`).

## License
Fill in according to your distribution policy (not provided in this repository).
