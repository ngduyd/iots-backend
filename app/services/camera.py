from app.services.image_analysis_service import process_camera_frame
from app.core import config
import asyncio

async def process_camera_stream(camera_id: str, secret: str):
    """
    Capture frame from camera URL and process with people counting.
    Args:
        camera_id: Camera ID from database
        secret: Camera secret for authentication
    Returns:
        Analysis result dict or None
    """
    import requests
    
    snapshot_url = f"{config.API_SNAPSHOT_URL}/{camera_id}.jpg"
    print(f"Capturing snapshot for camera {camera_id} from API", flush=True)

    try:
        response = await asyncio.to_thread(requests.get, snapshot_url, timeout=15)
        response.raise_for_status()
        
        frame_data = response.content
        return await process_camera_frame(camera_id, frame_data)
    except requests.exceptions.Timeout:
        print(f"Request timeout capturing snapshot for camera {camera_id}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Required failed API snapshot for camera {camera_id}: {e}")
        return None
    except Exception as e:
        print(f"Error capturing snapshot for camera {camera_id}: {e}")
        return None