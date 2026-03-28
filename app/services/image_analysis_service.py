"""
Service for handling camera image analysis and people counting.
Signals AI server to pull camera frames and returns the count.
"""
import asyncio
import json
import os
from datetime import datetime

import requests

from app.core import config
from app.services.database import save_image_analysis, get_camera


# PEOPLE_COUNT_API_URL is loaded from config
PEOPLE_COUNT_TIMEOUT_SECONDS = 4

# In-memory cache for camera info (60s TTL to reduce DB load)
_camera_cache: dict = {}
_camera_cache_time: dict = {}


async def _get_camera_cached(camera_id: str):
    """Retrieve camera info from cache, refreshing if older than 60s."""
    now = asyncio.get_running_loop().time()
    cached_at = _camera_cache_time.get(camera_id, 0)
    if camera_id in _camera_cache and now - cached_at < 60:
        return _camera_cache[camera_id]
    camera = await get_camera(camera_id)
    _camera_cache[camera_id] = camera
    _camera_cache_time[camera_id] = now
    return camera


def _generate_image_id() -> str:
    """Generate a unique image ID using timestamp + random bytes."""
    ts = int(datetime.now().timestamp() * 1000)
    rand = os.urandom(8).hex()
    return f"{ts}_{rand}"


async def process_camera_frame(camera_id: str):
    """
    Trigger camera analysis on the AI server and store results in DB.

    Flow:
      1. Get camera info from cache / DB
      2. Call AI server with camera_id (AI server pulls the frame)
      3. Save people count result to the database
    """
    camera = await _get_camera_cached(camera_id)
    if not camera:
        print(f"[ANALYSIS] Camera {camera_id} not found")
        return None

    people_count = await _call_people_count_service(camera_id)
    if people_count is None:
        return None

    image_id = _generate_image_id()
    return await save_image_analysis(
        image_id=image_id,
        camera_id=camera_id,
        image_path=f"remote://{camera_id}/{image_id}",
        people_count=people_count,
        metadata={
            "camera_name": camera.get("name"),
            "branch_id": camera.get("branch_id"),
        },
    )


async def _call_people_count_service(camera_id: str) -> int | None:
    """
    Call AI server to perform people counting by camera_id.
    AI server is responsible for fetching the frame.

    Returns people count as int, or None on failure.
    """
    try:
        response_text = await asyncio.to_thread(
            _post_json,
            config.PEOPLE_COUNT_API_URL,
            {"camera_id": camera_id},
            PEOPLE_COUNT_TIMEOUT_SECONDS,
        )
        data = json.loads(response_text)
        count = data.get("people_count", 0)
        return count if isinstance(count, int) else 0

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


def _post_json(url: str, payload: dict, timeout: int) -> str:
    """Send a POST request with JSON payload and return response text."""
    resp = requests.post(url, json=payload, timeout=timeout)
    resp.raise_for_status()
    return resp.text
