import asyncio

from app.core import config
from app.services import manager
from app.services.database import save_message
from app.services.mqtt_client import create_mqtt_client


class MqttRuntime:
    def __init__(self):
        self.client = None
        self.loop = None
        self.message_queue = None
        self._offline_task = None
        self._db_worker_task = None
        self.running = False

    async def start(self):
        self.loop = asyncio.get_event_loop()
        self.message_queue = asyncio.Queue()

        print("Connecting to MQTT broker...")
        self.client = create_mqtt_client(self.loop, self.message_queue)
        self.client.connect(config.MQTT_BROKER, config.MQTT_PORT, 60)
        self.client.loop_start()

        self._offline_task = asyncio.create_task(self._offline_monitor())
        self._db_worker_task = asyncio.create_task(self._db_worker())
        self.running = True
        print("MQTT runtime started")

    async def stop(self):
        self.running = False

        for task in (self._offline_task, self._db_worker_task):
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
