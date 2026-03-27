from app.services.database import get_camera
from app.services.image_analysis_service import process_camera_frame
from app.core import config
import asyncio

async def process_camera_stream(camera_id: str, secret: str):
    """
    Capture frame from RTMP stream and process with people counting.
    Args:
        camera_id: Camera ID from database
        secret: Camera secret for authentication
    Returns:
        Analysis result dict or None
    """
    try:
        import cv2
    except Exception as e:
        print(f"OpenCV not available for camera {camera_id}: {e}")
        return None
    
    # Build RTMP URL from config so each camera can run independently.
    rtmp_url = f"{config.RTMP_BASE_URL.rstrip('/')}/{camera_id}?secret={secret}"
    print(f"Processing camera stream for {camera_id} at {rtmp_url}")
    
    try:
        # Open capture with timeout to prevent hanging
        cap = cv2.VideoCapture(rtmp_url)
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000)
    except Exception as e:
        print(f"Failed to open RTMP stream {camera_id}: {e}")
        return None
    
    try:
        if not cap.isOpened():
            return None
        
        # Read frame with asyncio timeout wrapper (10 seconds max)
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