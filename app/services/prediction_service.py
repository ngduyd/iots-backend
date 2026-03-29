import requests
import json
import asyncio
from urllib import error, request

from app.core import config
from app.repositories import job_repo

TRAIN_API_URL = f"{config.AI_API_URL}/train"

async def notify_ai_server_for_job(job_id: str, secret: str, data_batch: list, request_payload: dict):
    try:
        payload = {
            "job_id": job_id,
            "secret": secret,
            "dataset": request_payload.get("dataset"),
            "feature_engineering": request_payload.get("feature_engineering"),
            "forecast": request_payload.get("forecast"),
            "model_hyperparams": request_payload.get("model_hyperparams"),
            "data": data_batch
        }
        
        print(f"[PREDICTION-SERVICE] Notifying AI server for job {job_id} at {TRAIN_API_URL}")
        
        resp = requests.post(TRAIN_API_URL, json=payload, timeout=60)
        resp.raise_for_status()

        await job_repo.update_job_status(job_id, "running", message="Data sent to AI server, processing started")
        return True

    except Exception as e:
        error_msg = f"Failed to notify AI server: {str(e)}"
        print(f"[PREDICTION-SERVICE] Error: {error_msg}")
        await job_repo.update_job_status(job_id, "failed", message=error_msg)
        return False

async def get_prediction_status(job_id: str):
    # Logic để kiểm tra trạng thái từ AI server nếu có API
    pass

PREDICT_API_URL = f"{config.AI_API_URL}/predict"
PREDICT_TIMEOUT_SECONDS = 20

async def predict_branch(sensor_id: str, values: list, people: list, model_id: str = "default"):
    payload = {
        "senser_id": sensor_id,
        "rows": values,
        "model_id": model_id,
        "people": people,
    }

    req = request.Request(
        PREDICT_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        response_text = await asyncio.to_thread(_send_predict_request, req)
        return json.loads(response_text) if response_text else None
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        raise Exception(f"Prediction service returned HTTP {exc.code}: {body}")
    except error.URLError as exc:
        raise Exception(f"Cannot connect to prediction service: {exc.reason}")
    except json.JSONDecodeError:
        raise Exception("Prediction service returned invalid JSON")

def _send_predict_request(req: request.Request) -> str:
    with request.urlopen(req, timeout=PREDICT_TIMEOUT_SECONDS) as response:
        return response.read().decode("utf-8")
