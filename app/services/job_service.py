import requests
from datetime import datetime, timedelta

from app.core import config
from app.services.database import (
    get_branch_data_for_export,
    update_job_status_db
)

TRAIN_API_URL = f"{config.AI_API_URL}/train"

async def get_job_data_single_batch(branch_id: int, date_from: datetime, date_to: datetime):
    sensor_values, people_counts = await get_branch_data_for_export(branch_id, date_from, date_to)

    events = []
    for row in sensor_values:
        val_obj = row["value"]
        if isinstance(val_obj, str):
            try:
                import json
                val_obj = json.loads(val_obj)
            except:
                val_obj = {}

        events.append({
            "ts": row["created_at"].timestamp(),
            "data": val_obj if isinstance(val_obj, dict) else {}
        })

    for row in people_counts:
        events.append({
            "ts": row["created_at"].timestamp(),
            "data": {"people": row["people_count"]}
        })

    events.sort(key=lambda x: x["ts"])

    if not events:
        return []

    WINDOW_SECONDS = 5.0
    merged_windows = []
    
    current_window_ts = events[0]["ts"]
    current_window_data = {}
    
    for event in events:
        if event["ts"] - current_window_ts <= WINDOW_SECONDS:
            current_window_data.update(event["data"])
        else:
            merged_windows.append({
                "timestamp": current_window_ts,
                "data": current_window_data
            })
            current_window_ts = event["ts"]
            current_window_data = event["data"].copy()
    
    merged_windows.append({
        "timestamp": current_window_ts,
        "data": current_window_data
    })

    final_output = []
    current_state = {"co2": None, "temp": None, "rh": None, "people": None}
    
    for window in merged_windows:
        data = window["data"]
        for key in ["co2", "temp", "rh", "people"]:
            if key in data and data[key] is not None:
                current_state[key] = data[key]
        
        record = {"timestamp": window["timestamp"]}
        record.update(current_state.copy())
        final_output.append(record)

    return final_output

async def process_and_notify_ai_server(job_id: str, secret: str, branch_id: int, date_from: datetime, date_to: datetime, request_payload: dict):
    try:
        data_batch = await get_job_data_single_batch(branch_id, date_from, date_to)
        
        if not data_batch:
            await update_job_status_db(job_id, "failed", message="No data found for the selected time range")
            return

        payload = {
            "job_id": job_id,
            "secret": secret,
            "dataset": request_payload.get("dataset"),
            "feature_engineering": request_payload.get("feature_engineering"),
            "forecast": request_payload.get("forecast"),
            "model_hyperparams": request_payload.get("model_hyperparams"),
            "data": data_batch
        }
        print(f"[JOB-SERVICE] Notifying AI server for job {job_id} at {TRAIN_API_URL}")
        resp = requests.post(TRAIN_API_URL, json=payload, timeout=60)
        resp.raise_for_status()

        await update_job_status_db(job_id, "running", message="Data sent to AI server, processing started")
        print(f"[JOB-SERVICE] Job {job_id} successfully started by AI server")

    except Exception as e:
        error_msg = f"Failed to notify AI server: {str(e)}"
        print(f"[JOB-SERVICE] Error: {error_msg}")
        await update_job_status_db(job_id, "failed", message=error_msg)


def get_job_defaults_data():
    now = datetime.now()
    return {
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
