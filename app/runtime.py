import asyncio
import heapq
import random
import time as _time
import concurrent.futures

from app.core import config
from app.services.database import get_active_cameras, save_messages_batch
from app.services.mqtt_client import create_mqtt_client
from app.services.image_analysis_service import process_camera_frame


class MqttRuntime:
    def __init__(self):
        self.client = None
        self.loop = None
        self.message_queue = None
        self.running = False

        # Camera scheduler heap: (execution_time, camera_id)
        self._camera_heap: list = []
        # Currently scheduled camera IDs (O(1) lookup)
        self._scheduled_ids: set = set()
        # Count of concurrently running AI tasks
        self._active_count: int = 0

        self._db_worker_task = None
        self._camera_scheduler_task = None
        self._camera_refresh_task = None

    # Lifecycle management
    async def start(self):
        self.loop = asyncio.get_running_loop()

        # Expand thread pool to prevent asyncio.to_thread() from blocking
        pool_size = max(50, config.CAMERA_MAX_INFLIGHT * 2)
        self.loop.set_default_executor(
            concurrent.futures.ThreadPoolExecutor(max_workers=pool_size)
        )

        self.message_queue = asyncio.Queue(maxsize=max(1, config.MQTT_QUEUE_MAXSIZE))

        print("Connecting to MQTT broker...")
        self.client = create_mqtt_client(self.loop, self.message_queue)
        self.client.connect(config.MQTT_BROKER, config.MQTT_PORT, 60)
        self.client.loop_start()

        self._db_worker_task = asyncio.create_task(self._db_worker())
        self._camera_refresh_task = asyncio.create_task(self._camera_list_refresher())
        self._camera_scheduler_task = asyncio.create_task(self._camera_scheduler())
        self.running = True
        print("MQTT runtime started")

    async def stop(self):
        self.running = False

        for task in (
            self._db_worker_task,
            self._camera_scheduler_task,
            self._camera_refresh_task,
        ):
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            self.client = None

        print("MQTT runtime stopped")

    # DB worker task to save MQTT data in batches
    async def _db_worker(self):
        batch_size = max(1, config.DB_WORKER_BATCH_SIZE)
        flush_interval = max(0.01, config.DB_WORKER_FLUSH_INTERVAL_MS / 1000.0)

        while True:
            sensor_id, payload, received_at = await self.message_queue.get()
            batch = [(sensor_id, payload, received_at)]

            deadline = self.loop.time() + flush_interval
            while len(batch) < batch_size:
                remain = deadline - self.loop.time()
                if remain <= 0:
                    break
                try:
                    item = await asyncio.wait_for(self.message_queue.get(), timeout=remain)
                    batch.append(item)
                except asyncio.TimeoutError:
                    break

            try:
                await save_messages_batch(batch)
            except Exception as e:
                print(f"[DB] Error saving batch: {e}")
            finally:
                for _ in batch:
                    self.message_queue.task_done()

    def add_camera_to_schedule(self, camera_id: str):
        """Dynamically add a camera to the scheduling queue."""
        if not self.running or not self.loop:
            return
        if camera_id not in self._scheduled_ids:
            now = self.loop.time()
            jitter = random.uniform(0, max(0, config.CAMERA_CAPTURE_JITTER_SECONDS))
            heapq.heappush(self._camera_heap, (now + jitter, camera_id))
            self._scheduled_ids.add(camera_id)
            print(f"[SCHEDULER] Dynamically added camera {camera_id} (starting in {jitter:.1f}s)")

    def remove_camera_from_schedule(self, camera_id: str):
        """Dynamically remove a camera from the scheduling queue."""
        if camera_id in self._scheduled_ids:
            self._scheduled_ids.discard(camera_id)
            print(f"[SCHEDULER] Dynamically removed camera {camera_id} from schedule")

    # Camera list management tasks
    async def _fetch_and_merge_cameras(self):
        """Fetch cameras from DB and update the heap for new or removed ones."""
        try:
            rows = await get_active_cameras()
        except Exception as e:
            print(f"[SCHEDULER] Error fetching cameras from DB: {e}")
            return

        db_ids = {row["camera_id"] for row in rows}
        now = self.loop.time()

        new_ids = db_ids - self._scheduled_ids
        for camera_id in new_ids:
            jitter = random.uniform(0, max(0, config.CAMERA_CAPTURE_JITTER_SECONDS))
            heapq.heappush(self._camera_heap, (now + jitter, camera_id))
            self._scheduled_ids.add(camera_id)
            print(f"[SCHEDULER] Adding camera {camera_id} (starting in {jitter:.1f}s)")

        # Stale cameras remain in heap but are skipped when popped (lazy removal)
        removed_ids = self._scheduled_ids - db_ids
        for camera_id in removed_ids:
            self._scheduled_ids.discard(camera_id)
            print(f"[SCHEDULER] Removing camera {camera_id} from schedule")

        print(f"[SCHEDULER] {len(db_ids)} active cameras (+{len(new_ids)} new, -{len(removed_ids)} removed)")

    async def _camera_list_refresher(self):
        """Camera list is managed dynamically via API webhooks (verify-stream / end-stream).
        No polling needed — cameras start offline and join the schedule only when they connect.
        """
        # Initial fetch intentionally skipped: all cameras are reset to 'offline' on startup.
        # Cameras are added to the schedule dynamically when they call /verify-stream.
        pass

    # Main scheduler loop using heapq and fire-and-forget tasks
    async def _camera_scheduler(self):
        """
        Priority queue based scheduler. 
        Runs cameras independently without blocking.
        Deleted cameras are skipped when their turn comes.
        """
        # Wait for initial load
        await asyncio.sleep(0.1)

        while self.running:
            now = self.loop.time()

            while self._camera_heap and self._camera_heap[0][0] <= now:
                due_at, camera_id = heapq.heappop(self._camera_heap)

                # Skip removed cameras
                if camera_id not in self._scheduled_ids:
                    continue

                # Soft limit on concurrent tasks
                if self._active_count >= config.CAMERA_MAX_INFLIGHT:
                    heapq.heappush(self._camera_heap, (now + 0.5, camera_id))
                    break

                self._active_count += 1
                task = asyncio.create_task(self._run_one(camera_id))
                task.add_done_callback(self._on_task_done)

                # Schedule next run
                next_run = now + max(1, config.CAMERA_CAPTURE_INTERVAL_SECONDS)
                heapq.heappush(self._camera_heap, (next_run, camera_id))

            # Sleep until next task (max 1s to remain responsive)
            if self._camera_heap:
                sleep_for = self._camera_heap[0][0] - self.loop.time()
                await asyncio.sleep(max(0.0, min(sleep_for, 1.0)))
            else:
                await asyncio.sleep(1.0)

    def _on_task_done(self, task: asyncio.Task):
        self._active_count -= 1
        try:
            task.result()
        except (asyncio.CancelledError, Exception):
            pass  # Logged within _run_one

    async def _run_one(self, camera_id: str):
        """Analyze a single camera - independent task with hard timeout."""
        t0 = _time.monotonic()
        try:
            await asyncio.wait_for(
                process_camera_frame(camera_id),
                timeout=config.CAMERA_CAPTURE_TASK_TIMEOUT_SECONDS,
            )
            print(f"[SCHEDULER] {camera_id} completed in {_time.monotonic() - t0:.2f}s")
        except asyncio.TimeoutError:
            print(f"[SCHEDULER] {camera_id} TIMEOUT after {_time.monotonic() - t0:.2f}s")
        except Exception as e:
            print(f"[SCHEDULER] {camera_id} error after {_time.monotonic() - t0:.2f}s: {e}")


# Singleton instance — import from here to avoid circular imports with app.main
runtime = MqttRuntime()
