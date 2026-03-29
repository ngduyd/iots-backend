from datetime import datetime

from app.repositories import sensor_repo, branch_repo

async def get_sensors(limit: int = 100, group_id: int = None):
    return await sensor_repo.get_sensors(limit, group_id)

async def get_sensor(sensor_id: str, group_id: int = None):
    return await sensor_repo.get_sensor(sensor_id, group_id)

async def get_sensors_by_branch(branch_id: int, limit: int = 100):
    return await sensor_repo.get_sensors_by_branch(branch_id, limit)

async def add_sensor(name: str = None, branch_id: int = None):
    return await sensor_repo.add_sensor(name, branch_id)

async def update_sensor(sensor_id: str, name: str = None, branch_id: int = None, delete: bool = False):
    return await sensor_repo.update_sensor(sensor_id, name, branch_id, delete)

async def get_sensor_values(
    sensor_id: str, 
    limit: int = 1000, 
    group_id: int = None, 
    from_time: datetime = None, 
    to_time: datetime = None
):
    return await sensor_repo.get_sensor_values(sensor_id, limit, group_id, from_time, to_time)

async def get_branch_data_for_export(branch_id: int, from_time: datetime, to_time: datetime):
    return await branch_repo.get_branch_data_for_export(branch_id, from_time, to_time)

async def get_sensor_to_branch_mapping():
    return await sensor_repo.get_sensor_to_branch_mapping()

async def get_all_sensor_status():
    return await sensor_repo.get_all_sensor_status()

async def update_sensor_status(sensor_id: str, status: str):
    return await sensor_repo.update_sensor_status(sensor_id, status)
