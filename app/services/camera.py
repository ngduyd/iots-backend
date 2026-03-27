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
    import sys
    import shlex
    # Build RTMP URL from config so each camera can run independently.
    rtmp_url = f"{config.RTMP_BASE_URL.rstrip('/')}/{camera_id}?secret={secret}"
    print(f"Capturing camera stream for {camera_id} using ffmpeg", flush=True)

    # Prepare ffmpeg command to grab 1 frame as JPEG to stdout
    ffmpeg_cmd = [
        "ffmpeg",
        "-loglevel", "error",
        "-fflags", "nobuffer",
        "-flags", "low_delay",
        "-rtsp_transport", "tcp",
        "-i", rtmp_url,
        "-frames:v", "1",
        "-f", "image2",
        "-vcodec", "mjpeg",
        "pipe:1"
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *ffmpeg_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            print(f"ffmpeg timeout for camera {camera_id}")
            return None
        if proc.returncode != 0 or not stdout:
            print(f"ffmpeg failed for camera {camera_id}: {stderr.decode(errors='ignore')}")
            return None
        frame_data = stdout
        return await process_camera_frame(camera_id, frame_data)
    except Exception as e:
        print(f"Error running ffmpeg for camera {camera_id}: {e}")
        return None