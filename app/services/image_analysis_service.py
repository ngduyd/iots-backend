import asyncio
import json
import requests

from app.core import config
from app.repositories import camera_repo


PEOPLE_COUNT_API_URL = f"{config.AI_API_URL}/count-people"
PEOPLE_COUNT_TIMEOUT_SECONDS = 4

_camera_cache: dict = {}
_camera_cache_time: dict = {}


async def _get_camera_cached(camera_id: str):
    now = asyncio.get_running_loop().time()
    cached_at = _camera_cache_time.get(camera_id, 0)
    if camera_id in _camera_cache and now - cached_at < 60:
        return _camera_cache[camera_id]
    camera = await camera_repo.get_camera(camera_id)
    _camera_cache[camera_id] = camera
    _camera_cache_time[camera_id] = now
    return camera


async def process_camera_frame(camera_id: str):
    camera = await _get_camera_cached(camera_id)
    if not camera:
        print(f"[ANALYSIS] Camera {camera_id} not found")
        return None

    response = await _call_people_count_service(camera_id)
    if response is None:
        return None

    return await camera_repo.save_image_analysis(
        image_id=response.get("image_id"),
        camera_id=camera_id,
        image_path=response.get("image_path"),
        people_count=response.get("people_count"),
        metadata={
            "camera_name": camera.get("name"),
            "branch_id": camera.get("branch_id"),
        },
    )


async def _call_people_count_service(camera_id: str) -> dict | None:
    try:
        response_text = await asyncio.to_thread(
            _post_form,
            PEOPLE_COUNT_API_URL,
            {"camera_id": camera_id},
            PEOPLE_COUNT_TIMEOUT_SECONDS,
        )
        data = json.loads(response_text)
        return data

    except requests.exceptions.Timeout:
        print(f"[ANALYSIS] {camera_id}: timeout after {PEOPLE_COUNT_TIMEOUT_SECONDS}s")
    except requests.exceptions.HTTPError as exc:
        print(f"[ANALYSIS] {camera_id}: HTTP {exc.response.status_code} - {exc.response.text[:120]}")
    except requests.exceptions.ConnectionError as exc:
        print(f"[ANALYSIS] {camera_id}: connection error - {exc}")
    except json.JSONDecodeError:
        print(f"[ANALYSIS] {camera_id}: invalid JSON response")
    except Exception as exc:
        print(f"[ANALYSIS] {camera_id}: unexpected error - {exc}")

    return None


def _post_form(url: str, payload: dict, timeout: int) -> str:
    resp = requests.post(url, data=payload, timeout=timeout)
    resp.raise_for_status()
    return resp.text
