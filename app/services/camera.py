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
    import av
    # Build RTMP URL from config so each camera can run independently.
    rtmp_url = f"{config.RTMP_BASE_URL.rstrip('/')}/{camera_id}?secret={secret}"
    print(f"Capturing camera stream for {camera_id}", flush=True)

    container = None
    try:
        # Open stream with timeout using thread to avoid blocking event loop
        container = await asyncio.wait_for(
            asyncio.to_thread(av.open, rtmp_url),
            timeout=10,
        )
    except Exception as e:
        print(f"Failed to open RTMP stream {camera_id} with PyAV: {e}")
        return None

    frame_data = None
    try:
        # Decode first video frame
        for frame in container.decode(video=0):
            img = frame.to_ndarray(format="bgr24")
            import cv2
            ok, buffer = cv2.imencode('.jpg', img)
            if not ok:
                print(f"Failed to encode frame for camera {camera_id}")
                return None
            frame_data = buffer.tobytes()
            break
        if frame_data is None:
            print(f"No frame decoded for camera {camera_id}")
            return None
        return await process_camera_frame(camera_id, frame_data)
    except Exception as e:
        print(f"Error decoding frame for camera {camera_id}: {e}")
        return None
    finally:
        if container is not None:
            container.close()