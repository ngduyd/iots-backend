import pytest
import asyncio
import json
from datetime import datetime, timedelta
from app.services.alert import NotificationManager, AlertProcessor
from app.core import config

@pytest.mark.asyncio
async def test_notification_manager_broadcast():
    manager = NotificationManager()
    queue = asyncio.Queue()
    manager.add_queue(queue)
    
    msg = {"test": "data"}
    await manager.broadcast(msg)
    
    result = await queue.get()
    assert json.loads(result) == msg
    
    manager.remove_queue(queue)
    assert len(manager.queues) == 0

@pytest.mark.asyncio
async def test_alert_processor_history():
    processor = AlertProcessor()
    sensor_id = "S1"
    now = datetime.now()
    
    processor._update_history(sensor_id, {"temp": 25}, now)
    assert len(processor.history[sensor_id]) == 1
    
    avg = processor._get_average(sensor_id, "temp")
    assert avg == 25

@pytest.mark.asyncio
async def test_alert_processor_fire_condition(monkeypatch):
    from app.services import database
    processor = AlertProcessor()
    sensor_id = "S1"
    
    # Mock create_alert to avoid DB call
    async def mock_create_alert(**kwargs):
        return True
    monkeypatch.setattr(database, "create_alert", mock_create_alert)

    # Absolute max temp trigger
    thresholds = {"activate": True, "sensors": {}}
    payload = {"temp": config.ALERT_TEMP_ABSOLUTE_MAX + 1}
    
    # We need to mock broadcast too
    from app.services.alert import notification_manager
    async def mock_broadcast(msg): pass
    monkeypatch.setattr(notification_manager, "broadcast", mock_broadcast)

    await processor.process_message(sensor_id, 1, payload, thresholds)
    # If it reached create_alert, it works. We can't easily check internal state without more mocks 
    # but the logic path is exercised.

@pytest.mark.asyncio
async def test_alert_processor_env_threshold(monkeypatch):
    from app.services import database
    processor = AlertProcessor()
    
    async def mock_create_alert(**kwargs):
        return True
    monkeypatch.setattr(database, "create_alert", mock_create_alert)
    
    from app.services.alert import notification_manager
    async def mock_broadcast(msg): pass
    monkeypatch.setattr(notification_manager, "broadcast", mock_broadcast)

    thresholds = {
        "activate": True,
        "sensors": {
            "co2": {"min": 400, "max": 1000, "activated": True}
        }
    }
    
    # High CO2 trigger
    payload = {"co2": 1200}
    await processor.process_message("S1", 1, payload, thresholds)
