import asyncio

from app.core import config
from app.services import manager
from app.services.database import get_active_cameras, save_message
from app.services.mqtt_client import create_mqtt_client
from app.services.camera import process_camera_stream


class MqttRuntime:
    def __init__(self):
        self.client = None
        self.loop = None
        self.message_queue = None
        self._offline_task = None
        self._db_worker_task = None
        # self._camera_scheduler_task = None
        # self._camera_workers = {}
        # self._camera_secrets = {}
        self.running = False

    async def start(self):
        self.loop = asyncio.get_event_loop()
        self.message_queue = asyncio.Queue()

        print("Connecting to MQTT broker...")
        self.client = create_mqtt_client(self.loop, self.message_queue)
        self.client.connect(config.MQTT_BROKER, config.MQTT_PORT, 60)
        self.client.loop_start()

        # self._offline_task = asyncio.create_task(self._offline_monitor())
        # self._db_worker_task = asyncio.create_task(self._db_worker())
        # self._camera_scheduler_task = asyncio.create_task(self._camera_scheduler())
        self.running = True
        print("MQTT runtime started")

    async def stop(self):
        self.running = False

        for task in (self._offline_task, self._db_worker_task, self._camera_scheduler_task):
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # for task in self._camera_workers.values():
        #     task.cancel()
        # for task in self._camera_workers.values():
        #     try:
        #         await task
        #     except asyncio.CancelledError:
        #         pass
        # self._camera_workers.clear()
        # self._camera_secrets.clear()

        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            self.client = None

        print("MQTT runtime stopped")

    async def _offline_monitor(self):
        while True:
            await asyncio.sleep(1)
            manager.check_offline_sensors(config.SENSOR_OFFLINE_TIMEOUT, self.loop)

    async def _db_worker(self):
        while True:
            sensor_id, payload, received_at = await self.message_queue.get()
            try:
                await save_message(sensor_id, payload, received_at)
            except Exception as e:
                print(f"Error saving message to db: {e}")
            finally:
                self.message_queue.task_done()

    # async def _camera_scheduler(self):
    #     while True:
    #         try:
    #             rows = await get_active_cameras()
    #             desired_ids = {row["camera_id"] for row in rows}

    #             for row in rows:
    #                 camera_id = row["camera_id"]
    #                 secret = row.get("secret")
    #                 current_secret = self._camera_secrets.get(camera_id)

    #                 # Start a worker for new active camera or restart when secret changes.
    #                 if camera_id not in self._camera_workers or current_secret != secret:
    #                     old_task = self._camera_workers.get(camera_id)
    #                     if old_task:
    #                         old_task.cancel()
    #                     self._camera_secrets[camera_id] = secret
    #                     self._camera_workers[camera_id] = asyncio.create_task(
    #                         self._camera_worker(camera_id, secret)
    #                     )

    #             inactive_ids = [camera_id for camera_id in self._camera_workers if camera_id not in desired_ids]
    #             for camera_id in inactive_ids:
    #                 task = self._camera_workers.pop(camera_id)
    #                 self._camera_secrets.pop(camera_id, None)
    #                 task.cancel()
    #         except Exception as e:
    #             print(f"Error in camera scheduler: {e}")

    #         await asyncio.sleep(config.CAMERA_SCHEDULER_POLL_SECONDS)

    # async def _camera_worker(self, camera_id: str, secret: str | None):
    #     while True:
    #         try:
    #             await process_camera_stream(camera_id, secret or "")
    #         except Exception as e:
    #             print(f"Error processing camera stream {camera_id}: {e}")

    #         await asyncio.sleep(config.CAMERA_CAPTURE_INTERVAL_SECONDS)
