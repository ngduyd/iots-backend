from app.repositories import camera_repo

async def get_cameras(limit: int = 100, group_id: int = None):
    return await camera_repo.get_cameras(limit, group_id)

async def get_active_cameras():
    return await camera_repo.get_active_cameras()

async def get_camera(camera_id: str, group_id: int = None):
    return await camera_repo.get_camera(camera_id, group_id)

async def add_camera(name: str = None, branch_id: int = None, activate: bool = False):
    return await camera_repo.add_camera(name, branch_id, activate)

async def update_camera(camera_id: str, name: str = None, branch_id: int = None, activate: bool = None):
    return await camera_repo.update_camera(camera_id, name, branch_id, activate)

async def delete_camera(camera_id: str):
    return await camera_repo.delete_camera(camera_id)

async def verify_camera_stream(camera_id: str, secret: str):
    return await camera_repo.verify_camera_stream(camera_id, secret)

async def end_camera_stream(camera_id: str, secret: str):
    return await camera_repo.end_camera_stream(camera_id, secret)

async def create_camera_access_request(camera_id: str, user_id: int, ttl_seconds: int = 60):
    return await camera_repo.create_camera_access_request(camera_id, user_id, ttl_seconds)

async def verify_camera_access_request_by_token(access_token: str, ttl_seconds: int = 60):
    return await camera_repo.verify_camera_access_request_by_token(access_token, ttl_seconds)

async def reset_all_cameras_offline():
    return await camera_repo.reset_all_cameras_offline()

async def get_cameras_by_branch(branch_id: int, limit: int = 100):
    return await camera_repo.get_cameras_by_branch(branch_id, limit)

async def get_camera_by_branch(branch_id: int):
    return await camera_repo.get_camera_by_branch(branch_id)

async def get_latest_people_count_by_branch(branch_id: int):
    return await camera_repo.get_latest_people_count_by_branch(branch_id)
