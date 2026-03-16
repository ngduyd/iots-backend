import asyncio

from app.core import config
from app.services import manager
from app.services.database import init_db
from app.services.mqtt_client import create_mqtt_client


class MqttRuntime:
    def __init__(self):
        self.client = None
        self.loop = None
        self._offline_task = None
        self.running = False
        self.db_ready = False

    async def start(self):
        await asyncio.sleep(1)
        self.loop = asyncio.get_event_loop()

        print("Initializing database...")
        await init_db()
        self.db_ready = True
        await manager.init()

        print("Connecting to MQTT broker...")
        self.client = create_mqtt_client(self.loop)
        self.client.connect(config.MQTT_BROKER, config.MQTT_PORT, 60)
        self.client.loop_start()

        self._offline_task = asyncio.create_task(self._offline_monitor())
        self.running = True
        print("MQTT runtime started")

    async def stop(self):
        self.running = False

        if self._offline_task:
            self._offline_task.cancel()
            try:
                await self._offline_task
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
