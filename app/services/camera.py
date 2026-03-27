from app.services.database import get_camera
from app.services.image_analysis_service import process_camera_frame
from app.core import config
import cv2

async def process_camera_stream(camera_id: str, secret: str):
    """
    Capture frame from RTMP stream and process with people counting.
    
    This function needs to be filled in with cv2 RTMP stream handling:
    
    Args:
        camera_id: Camera ID from database
        secret: Camera secret for authentication
    
    Returns:
        Analysis result dict or None
    """
    # Build RTMP URL from config so each camera can run independently.
    rtmp_url = f"{config.RTMP_BASE_URL.rstrip('/')}/{camera_id}?secret={secret}"

    cap = cv2.VideoCapture(rtmp_url)
    try:
        if not cap.isOpened():
            return None

        ret, frame = cap.read()
        if not ret:
            return None

        ok, buffer = cv2.imencode('.jpg', frame)
        if not ok:
            return None

        frame_data = buffer.tobytes()
        return await process_camera_frame(camera_id, frame_data)
    finally:
        cap.release()