import asyncio
import heapq
import random
import json
import time as _time
import concurrent.futures
from app.core import config
from app.services.database import (
    get_active_cameras,
    save_messages_batch,
    get_sensor_to_branch_mapping,
    get_all_branch_thresholds,
    update_branch_thresholds,
    DEFAULT_THRESHOLDS,
)
from app.services.alert import alert_processor
from app.services.mqtt_client import create_mqtt_client
from app.services.image_analysis_service import process_camera_frame

import traceback

class MqttRuntime:
    def __init__(self):
        self.client = None
        self.loop = None
        self.message_queue = None
        self.running = False

        self._camera_heap: list = []
        self._scheduled_ids: set = set()
        self._active_count: int = 0

        self._db_worker_task = None
        self._camera_scheduler_task = None

        self._sensor_to_branch: dict = {}
        self._threshold_cache: dict = {}
        

    async def start(self):
        self.loop = asyncio.get_running_loop()

        pool_size = max(50, config.CAMERA_MAX_INFLIGHT * 2)
        self.loop.set_default_executor(
            concurrent.futures.ThreadPoolExecutor(max_workers=pool_size)
        )

        self.message_queue = asyncio.Queue(maxsize=max(1, config.MQTT_QUEUE_MAXSIZE))

        print("Connecting to MQTT broker...")
        self.client = create_mqtt_client(self.loop, self.message_queue)
        self.client.connect(config.MQTT_BROKER, config.MQTT_PORT, 60)
        self.client.loop_start()

        await self._load_metadata_caches()

        self._db_worker_task = asyncio.create_task(self._db_worker())
        self._camera_scheduler_task = asyncio.create_task(self._camera_scheduler())
        self.running = True
        print("MQTT runtime started")

    async def stop(self):
        self.running = False

        for task in (
            self._db_worker_task,
            self._camera_scheduler_task,
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

    async def _load_metadata_caches(self):
        try:
            self._sensor_to_branch = await get_sensor_to_branch_mapping()
            self._threshold_cache = await get_all_branch_thresholds()
            print(f"[CACHE] Loaded {len(self._sensor_to_branch)} sensors and {len(self._threshold_cache)} branch thresholds")
        except Exception as e:
            print(f"[CACHE] Error loading metadata caches: {e}")

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
            for sid, pld, _ in batch:
                await self._process_threshold_discovery(sid, pld)

                branch_id = self._sensor_to_branch.get(sid)
                if branch_id:
                    try:
                        data = json.loads(pld)
                        thresholds = self._threshold_cache.get(branch_id, {})
                        await alert_processor.process_message(sid, branch_id, data, thresholds)
                    except Exception as e:
                        print(f"[ALERT] Error processing alerts for {sid}: {e}")
                        traceback.print_exc()

            try:
                await save_messages_batch(batch)
            except Exception as e:
                print(f"[DB] Error saving batch: {e}")
            finally:
                for _ in batch:
                    self.message_queue.task_done()

    async def _process_threshold_discovery(self, sensor_id: str, payload_str: str):
        try:
            branch_id = self._sensor_to_branch.get(sensor_id)
            if branch_id is None:
                self._sensor_to_branch = await get_sensor_to_branch_mapping()
                branch_id = self._sensor_to_branch.get(sensor_id)
                if branch_id is None:
                    return

            data = json.loads(payload_str)
            if not isinstance(data, dict):
                return

            thresholds = self._threshold_cache.get(branch_id, {})
            if "sensors" not in thresholds:
                thresholds["sensors"] = {}
            if "activate" not in thresholds:
                thresholds["activate"] = False

            sensors = thresholds["sensors"]
            needs_update = False
            for key in data.keys():
                if key not in sensors:
                    default = DEFAULT_THRESHOLDS.get(key, {"min": 0, "max": 100, "activated": True})
                    sensors[key] = {
                        "min": default["min"],
                        "max": default["max"],
                        "activated": True
                    }
                    needs_update = True

            if needs_update:
                self._threshold_cache[branch_id] = thresholds
                await update_branch_thresholds(branch_id, thresholds)
                print(f"[THRESHOLD] Discovered new parameters for branch {branch_id}: {list(data.keys())}")

        except Exception as e:
            pass

    def add_camera_to_schedule(self, camera_id: str):
        if not self.running or not self.loop:
            return
        if camera_id not in self._scheduled_ids:
            now = self.loop.time()
            jitter = random.uniform(0, max(0, config.CAMERA_CAPTURE_JITTER_SECONDS))
            heapq.heappush(self._camera_heap, (now + jitter, camera_id))
            self._scheduled_ids.add(camera_id)
            print(f"[SCHEDULER] Dynamically added camera {camera_id} (starting in {jitter:.1f}s)")

    def remove_camera_from_schedule(self, camera_id: str):
        if camera_id in self._scheduled_ids:
            self._scheduled_ids.discard(camera_id)
            print(f"[SCHEDULER] Dynamically removed camera {camera_id} from schedule")

    async def _fetch_and_merge_cameras(self):
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

        removed_ids = self._scheduled_ids - db_ids
        for camera_id in removed_ids:
            self._scheduled_ids.discard(camera_id)

    async def _camera_scheduler(self):
        await asyncio.sleep(0.1)

        while self.running:
            now = self.loop.time()

            while self._camera_heap and self._camera_heap[0][0] <= now:
                due_at, camera_id = heapq.heappop(self._camera_heap)

                if camera_id not in self._scheduled_ids:
                    continue

                if self._active_count >= config.CAMERA_MAX_INFLIGHT:
                    heapq.heappush(self._camera_heap, (now + 0.5, camera_id))
                    break

                self._active_count += 1
                task = asyncio.create_task(self._run_one(camera_id))
                task.add_done_callback(self._on_task_done)

                next_run = now + max(1, config.CAMERA_CAPTURE_INTERVAL_SECONDS)
                heapq.heappush(self._camera_heap, (next_run, camera_id))

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
            pass

    async def _run_one(self, camera_id: str):
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


runtime = MqttRuntime()
