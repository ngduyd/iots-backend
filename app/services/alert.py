import asyncio
import json
from datetime import datetime, timedelta
from collections import deque
from app.core import config
from app.services.database import update_branch_thresholds, DEFAULT_THRESHOLDS, create_alert

class NotificationManager:
    def __init__(self):
        self.queues = set()

    def add_queue(self, queue: asyncio.Queue):
        self.queues.add(queue)

    def remove_queue(self, queue: asyncio.Queue):
        self.queues.discard(queue)

    async def broadcast(self, message: dict):
        if not self.queues:
            return
        
        data = json.dumps(message)
        for q in list(self.queues):
            try:
                q.put_nowait(data)
            except asyncio.QueueFull:
                pass

notification_manager = NotificationManager()

class AlertProcessor:
    def __init__(self):
        self.history = {}
        self.history_window = timedelta(seconds=60)

    def _update_history(self, sensor_id: str, data: dict, now: datetime):
        if sensor_id not in self.history:
            self.history[sensor_id] = deque()
        
        history_dq = self.history[sensor_id]
        history_dq.append((now, data))

        cutoff = now - self.history_window
        while history_dq and history_dq[0][0] < cutoff:
            history_dq.popleft()

    def _get_average(self, sensor_id: str, key: str):
        history_dq = self.history.get(sensor_id)
        if not history_dq:
            return None
        
        values = [d.get(key) for _, d in history_dq if d.get(key) is not None]
        if not values:
            return None
        
        return sum(values) / len(values)

    def _get_delta_30s(self, sensor_id: str, key: str, now: datetime):
        history_dq = self.history.get(sensor_id)
        if not history_dq:
            return 0
        
        cutoff = now - timedelta(seconds=config.ALERT_TEMP_WINDOW)
        old_val = None
        for timestamp, d in history_dq:
            if timestamp >= cutoff:
                old_val = d.get(key)
                break
        
        if old_val is None:
            return 0
        
        current_val = history_dq[-1][1].get(key)
        if current_val is None:
            return 0
            
        return current_val - old_val

    async def process_message(self, sensor_id: str, branch_id: int, payload: dict, thresholds: dict):
        now = datetime.now()
        self._update_history(sensor_id, payload, now)

        # 0. Check Global Activation Flag
        if isinstance(thresholds, str):
            thresholds = json.loads(thresholds)
            
        if not thresholds.get("activate", False):
            return

        level = "STATUS"
        message = "Bình thường"
        details = {}

        # 1. Check Fire Condition (Priority 1)
        is_fire = False
        fire_reasons = []
        
        sensors_thresholds = thresholds.get("sensors", {})

        # Temp Check
        temp = payload.get("temp")
        if temp is not None:
            if temp >= config.ALERT_TEMP_ABSOLUTE_MAX:
                is_fire = True
                fire_reasons.append(f"Nhiệt độ quá cao ({temp}°C)")
            
            temp_delta = self._get_delta_30s(sensor_id, "temp", now)
            if temp_delta >= config.ALERT_TEMP_DELTA_MAX:
                is_fire = True
                fire_reasons.append(f"Nhiệt độ tăng vọt (+{temp_delta}°C)")

        # Pollutant Check (CO2, PM)
        for key in ["co2", "pm2_5", "pm10"]:
            val = payload.get(key)
            if val is not None:
                avg = self._get_average(sensor_id, key)
                # Check against nested sensors_thresholds
                if avg and val > (avg * config.ALERT_POLLUTANT_SPIKE_RATIO) and val > (sensors_thresholds.get(key, {}).get("max", 0) or 0):
                    is_fire = True
                    fire_reasons.append(f"{key.upper()} tăng vọt ({val} > avg {avg:.1f})")

        if is_fire:
            level = "CRITICAL"
            message = "CẢNH BÁO HỎA HOẠN: " + ", ".join(fire_reasons)
        else:
            # 2. Check Environment thresholds (Priority 2)
            warning_reasons = []
            for key, val in payload.items():
                if key in sensors_thresholds:
                    t = sensors_thresholds[key]
                    if not t.get("activated", True):
                        continue
                        
                    t_min = t.get("min")
                    t_max = t.get("max")
                    
                    if t_min is not None and val < t_min:
                        warning_reasons.append(f"{key} thấp ({val} < {t_min})")
                    if t_max is not None and val > t_max:
                        warning_reasons.append(f"{key} cao ({val} > {t_max})")
            
            if warning_reasons:
                level = "WARNING"
                message = "Cảnh báo môi trường: " + ", ".join(warning_reasons)

        # 3. Persistence & Broadcast
        notification = {
            "sensor_id": sensor_id,
            "branch_id": branch_id,
            "level": level,
            "message": message,
            "data": payload,
            "timestamp": now.isoformat()
        }

        await notification_manager.broadcast(notification)

        await create_alert(
            branch_id=branch_id,
            message=message,
            level=level
        )

alert_processor = AlertProcessor()