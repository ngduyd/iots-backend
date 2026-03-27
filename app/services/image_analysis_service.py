"""
Service for handling camera image analysis and people counting.
Sends camera frames to remote service for analysis.
"""
import asyncio
import json
import os
from datetime import datetime
import requests

from app.services.database import save_image_analysis, get_camera


PEOPLE_COUNT_API_URL = "http://100.123.114.97:9000/api/v1/count-people"
PEOPLE_COUNT_TIMEOUT_SECONDS = 8  # Reduced from 30s for faster fail-fast

# Simple in-memory cache for camera info (60s TTL)
_camera_cache = {}
_camera_cache_time = {}


async def _get_camera_cached(camera_id: str):
    """Get camera info with caching to reduce DB queries."""
    now = asyncio.get_running_loop().time()
    if camera_id in _camera_cache:
        cached_at = _camera_cache_time.get(camera_id, 0)
        if now - cached_at < 60:
            return _camera_cache[camera_id]
    
    camera = await get_camera(camera_id)
    _camera_cache[camera_id] = camera
    _camera_cache_time[camera_id] = now
    return camera


def _generate_image_id():
    """Generate unique image ID."""
    ts = int(datetime.now().timestamp() * 1000)
    rand = os.urandom(8).hex()
    return f"{ts}_{rand}"


async def process_camera_frame(camera_id: str, frame_data: bytes, metadata: dict = None):
    """
    Process a camera frame:
    1. Get camera info from DB
    2. Send frame + camera_id to people counting service (service will save)
    3. Receive counting result and metadata
    4. Save result to database
    
    Args:
        camera_id: Camera ID from database
        frame_data: Image frame bytes (from cv2 encoding)
        metadata: Optional metadata dict (e.g., {"fps": 30, "width": 1920, "height": 1080})
    
    Returns:
        dict with analysis result or None on error
    """
    import time
    start_time = time.time()
    try:
        # Get camera info (cached to avoid repeated DB queries)
        camera = await _get_camera_cached(camera_id)
        if not camera:
            print(f"[ANALYSIS] Camera {camera_id} not found")
            return None
        
        # Generate image ID
        image_id = _generate_image_id()
        
        # Send frame + camera_id to people counting service
        # Service will save the frame and return analysis result
        print(f"[ANALYSIS] Camera {camera_id} calling people count service (timeout {PEOPLE_COUNT_TIMEOUT_SECONDS}s)")
        people_count = await _call_people_count_service(camera_id, frame_data)
        
        if people_count is None:
            elapsed = time.time() - start_time
            print(f"[ANALYSIS] Camera {camera_id} failed to get people count after {elapsed:.2f}s")
            return None
        
        elapsed = time.time() - start_time
        print(f"[TIMING] Camera {camera_id} got people_count={people_count} in {elapsed:.2f}s")
        
        # Build metadata
        analysis_metadata = {
            "camera_name": camera.get("name"),
            "branch_id": camera.get("branch_id"),
            **(metadata or {})
        }
        
        # Placeholder path (service stores the actual frame)
        image_path = f"remote://{camera_id}/{image_id}"
        
        # Save analysis result to database
        result = await save_image_analysis(
            image_id=image_id,
            camera_id=camera_id,
            image_path=image_path,
            people_count=people_count,
            metadata=analysis_metadata,
        )
        
        return result
    
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"[ANALYSIS] Camera {camera_id} error after {elapsed:.2f}s: {type(e).__name__}: {e}")
        return None


async def _call_people_count_service(camera_id: str, frame_data: bytes) -> int | None:
    """
    Send frame to people counting service with camera_id using multipart/form-data.
    Service will save the frame and return count result.
    
    Args:
        camera_id: Camera ID to pass to service for tracking
        frame_data: Image frame bytes
    
    Returns:
        Number of people detected or None on error
    """
    import time
    start_time = time.time()
    try:
        # Prepare multipart form data
        files = {
            'camera_id': (None, camera_id),  # Form field
            'image': ('frame.jpg', frame_data, 'image/jpeg'),  # Binary file
        }
        
        print(f"[ANALYSIS] Camera {camera_id} sending frame ({len(frame_data)} bytes) to service")
        # Send request in thread to avoid blocking
        response_text = await asyncio.to_thread(
            _send_count_request, 
            PEOPLE_COUNT_API_URL, 
            files,
            PEOPLE_COUNT_TIMEOUT_SECONDS
        )
        elapsed = time.time() - start_time
        print(f"[TIMING] Camera {camera_id} service returned in {elapsed:.2f}s")
        response_data = json.loads(response_text)
        
        # Extract people count from response
        people_count = response_data.get("people_count", 0)
        return people_count if isinstance(people_count, int) else 0
    
    except requests.exceptions.Timeout:
        elapsed = time.time() - start_time
        print(f"[TIMING] Camera {camera_id} service TIMEOUT after {elapsed:.2f}s (limit {PEOPLE_COUNT_TIMEOUT_SECONDS}s)")
        return None
    except requests.exceptions.HTTPError as exc:
        elapsed = time.time() - start_time
        print(f"[ANALYSIS] Camera {camera_id} HTTP error {exc.response.status_code} after {elapsed:.2f}s: {exc.response.text[:100]}")
        return None
    except requests.exceptions.ConnectionError as exc:
        elapsed = time.time() - start_time
        print(f"[ANALYSIS] Camera {camera_id} connection error after {elapsed:.2f}s: {exc}")
        return None
    except json.JSONDecodeError:
        elapsed = time.time() - start_time
        print(f"[ANALYSIS] Camera {camera_id} invalid JSON response after {elapsed:.2f}s")
        return None
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"[ANALYSIS] Camera {camera_id} error after {elapsed:.2f}s: {type(e).__name__}: {e}")
        return None


def _send_count_request(url: str, files: dict, timeout: int) -> str:
    """Send multipart form-data POST request and return response text."""
    response = requests.post(url, files=files, timeout=timeout)
    response.raise_for_status()  # Raise exception on non-200 status
    return response.text
