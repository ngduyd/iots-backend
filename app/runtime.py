import asyncio
import random

from app.core import config
from app.services.database import get_active_cameras, save_messages_batch
from app.services.mqtt_client import create_mqtt_client
from app.services.camera import process_camera_stream


class MqttRuntime:
    def __init__(self):
        self.client = None
        self.loop = None
        self.message_queue = None
        self._db_worker_task = None
        self._camera_scheduler_task = None
        self._camera_running = set()
        self._camera_next_run = {}
        self._camera_capture_tasks = set()
        self._camera_semaphore = asyncio.Semaphore(max(1, config.CAMERA_MAX_CONCURRENT_CAPTURES))
        self.running = False

    async def start(self):
        self.loop = asyncio.get_event_loop()
        self.message_queue = asyncio.Queue(maxsize=max(1, config.MQTT_QUEUE_MAXSIZE))

        print("Connecting to MQTT broker...")
        self.client = create_mqtt_client(self.loop, self.message_queue)
        self.client.connect(config.MQTT_BROKER, config.MQTT_PORT, 60)
        self.client.loop_start()

        self._db_worker_task = asyncio.create_task(self._db_worker())
        self._camera_scheduler_task = asyncio.create_task(self._camera_scheduler())
        self.running = True
        print("MQTT runtime started")

    async def stop(self):
        self.running = False

        for task in (self._db_worker_task, self._camera_scheduler_task):
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        for task in list(self._camera_capture_tasks):
            task.cancel()
        for task in list(self._camera_capture_tasks):
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._camera_capture_tasks.clear()
        self._camera_running.clear()
        self._camera_next_run.clear()

        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            self.client = None

        print("MQTT runtime stopped")

    async def _db_worker(self):
        batch_size = max(1, config.DB_WORKER_BATCH_SIZE)
        flush_interval = max(0.01, config.DB_WORKER_FLUSH_INTERVAL_MS / 1000.0)

        while True:
            sensor_id, payload, received_at = await self.message_queue.get()
            batch = [(sensor_id, payload, received_at)]

            deadline = asyncio.get_running_loop().time() + flush_interval
            while len(batch) < batch_size:
                remain = deadline - asyncio.get_running_loop().time()
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
                print(f"Error saving message to db: {e}")
            finally:
                for _ in batch:
                    self.message_queue.task_done()

    async def _camera_scheduler(self):
        """Schedule one-shot camera captures with bounded concurrency.

        This avoids creating one infinite worker loop per camera, which is heavy
        when many cameras are active.
        """
        while True:
            try:
                rows = await get_active_cameras()
                active = {row["camera_id"]: (row.get("secret") or "") for row in rows}

                now = asyncio.get_running_loop().time()
                desired_ids = set(active.keys())

                for camera_id in list(self._camera_next_run.keys()):
                    if camera_id not in desired_ids:
                        self._camera_next_run.pop(camera_id, None)
                        self._camera_running.discard(camera_id)

                for camera_id in desired_ids:
                    if camera_id not in self._camera_next_run:
                        jitter = random.uniform(0, max(0, config.CAMERA_CAPTURE_JITTER_SECONDS))
                        self._camera_next_run[camera_id] = now + jitter

                due_ids = [
                    camera_id
                    for camera_id, due_at in self._camera_next_run.items()
                    if due_at <= now and camera_id in desired_ids and camera_id not in self._camera_running
                ]

                for camera_id in due_ids:
                    self._camera_running.add(camera_id)
                    self._camera_next_run[camera_id] = now + max(1, config.CAMERA_CAPTURE_INTERVAL_SECONDS)
                    print(f"[SCHEDULER] Camera {camera_id} queued (next at +{config.CAMERA_CAPTURE_INTERVAL_SECONDS}s)")
                    task = asyncio.create_task(self._capture_camera_once(camera_id, active[camera_id]))
                    self._camera_capture_tasks.add(task)
                    task.add_done_callback(lambda t, cid=camera_id: self._on_capture_done(cid, t))
            except Exception as e:
                print(f"Error in camera scheduler: {e}")

            await asyncio.sleep(max(1, config.CAMERA_SCHEDULER_POLL_SECONDS))

    async def _capture_camera_once(self, camera_id: str, secret: str):
        import time
        start_time = time.time()
        async with self._camera_semaphore:
            try:
                await asyncio.wait_for(
                    process_camera_stream(camera_id, secret),
                    timeout=max(1, config.CAMERA_CAPTURE_TASK_TIMEOUT_SECONDS),
                )
                elapsed = time.time() - start_time
                print(f"[TIMING] Camera {camera_id} capture completed in {elapsed:.2f}s")
            except asyncio.TimeoutError:
                elapsed = time.time() - start_time
                print(f"[TIMING] Camera {camera_id} capture TIMEOUT after {elapsed:.2f}s")
            except Exception as e:
                elapsed = time.time() - start_time
                print(f"[TIMING] Camera {camera_id} error after {elapsed:.2f}s: {e}")

    def _on_capture_done(self, camera_id: str, task: asyncio.Task):
        self._camera_capture_tasks.discard(task)
        self._camera_running.discard(camera_id)

        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception:
            pass
