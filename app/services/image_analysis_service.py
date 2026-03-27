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
PEOPLE_COUNT_TIMEOUT_SECONDS = 30


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
    try:
        # Get camera info
        camera = await get_camera(camera_id)
        if not camera:
            print(f"Camera {camera_id} not found")
            return None
        
        # Generate image ID
        image_id = _generate_image_id()
        
        # Send frame + camera_id to people counting service
        # Service will save the frame and return analysis result
        people_count = await _call_people_count_service(camera_id, frame_data)
        
        if people_count is None:
            print(f"Failed to get people count for {image_id}")
            return None
        
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
        print(f"Error processing camera frame: {e}")
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
    try:
        # Prepare multipart form data
        files = {
            'camera_id': (None, camera_id),  # Form field
            'image': ('frame.jpg', frame_data, 'image/jpeg'),  # Binary file
        }
        
        # Send request in thread to avoid blocking
        response_text = await asyncio.to_thread(
            _send_count_request, 
            PEOPLE_COUNT_API_URL, 
            files
        )
        response_data = json.loads(response_text)
        
        # Extract people count from response
        people_count = response_data.get("people_count", 0)
        return people_count if isinstance(people_count, int) else 0
    
    except requests.exceptions.HTTPError as exc:
        print(f"People count service HTTP error {exc.response.status_code}: {exc.response.text}")
        return None
    except requests.exceptions.ConnectionError as exc:
        print(f"Cannot connect to people count service: {exc}")
        return None
    except json.JSONDecodeError:
        print("People count service returned invalid JSON")
        return None
    except Exception as e:
        print(f"Error calling people count service: {e}")
        return None


def _send_count_request(url: str, files: dict) -> str:
    """Send multipart form-data POST request and return response text."""
    response = requests.post(url, files=files, timeout=PEOPLE_COUNT_TIMEOUT_SECONDS)
    response.raise_for_status()  # Raise exception on non-200 status
    return response.text
