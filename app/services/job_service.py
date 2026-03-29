from datetime import datetime, timedelta

from app.repositories import branch_repo, job_repo
from app.services import prediction_service

async def get_job_data_single_batch(branch_id: int, date_from: datetime, date_to: datetime):
    sensor_values, people_counts = await branch_repo.get_branch_data_for_export(branch_id, date_from, date_to)

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
    data_batch = await get_job_data_single_batch(branch_id, date_from, date_to)
    
    if not data_batch:
        await job_repo.update_job_status(job_id, "failed", message="No data found for the selected time range")
        return

    # Sử dụng prediction_service để gọi đến AI server
    await prediction_service.notify_ai_server_for_job(job_id, secret, data_batch, request_payload)

async def create_job(job_id, branch_id, user_id, secret, dataset_params, feature_params, forecast_params, model_params):
    return await job_repo.create_job(job_id, branch_id, user_id, secret, dataset_params, feature_params, forecast_params, model_params)

async def get_job(job_id: str):
    return await job_repo.get_job(job_id)

async def get_jobs(group_id: int = None, status: str = None, limit: int = 100):
    return await job_repo.get_jobs(group_id, status, limit)

async def cancel_job(job_id: str):
    return await job_repo.cancel_job(job_id)

async def get_models(group_id: int):
    return await job_repo.get_models(group_id)

async def update_model_name(model_id: str, name: str, group_id: int):
    return await job_repo.update_model_name(model_id, name, group_id)

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
