import asyncio
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.services.alert import notification_manager

router = APIRouter(prefix="/notifications", tags=["notifications"])

async def event_generator():
    queue = asyncio.Queue()
    notification_manager.add_queue(queue)
    try:
        while True:
            data = await queue.get()
            yield f"data: {data}\n\n"
    except asyncio.CancelledError:
        notification_manager.remove_queue(queue)
        raise

@router.get("/stream")
async def stream_notifications():
    """
    Server-Sent Events (SSE) endpoint to listen for real-time sensor alerts.
    """
    return StreamingResponse(event_generator(), media_type="text/event-stream")
