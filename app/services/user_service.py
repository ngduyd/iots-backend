from app.repositories import user_repo

async def get_user(user_id: int):
    return await user_repo.get_user(user_id)

async def get_user_by_username(username: str):
    return await user_repo.get_user_by_username(username)

async def authenticate_user(username, password):
    return await user_repo.authenticate_user(username, password)

async def create_user(username, password, group_id=None, role="user"):
    return await user_repo.create_user(username, password, group_id, role)

async def update_user(user_id, username=None, group_id=None, role=None, password=None):
    existing = await user_repo.get_user(user_id)
    if not existing:
        return None
    
    return await user_repo.update_user(
        user_id=user_id,
        username=username or existing["username"],
        group_id=group_id if group_id is not None else existing["group_id"],
        role=role or existing["role"],
        password=password
    )

async def delete_user(user_id: int):
    return await user_repo.delete_user(user_id)

async def get_users(group_id: int = None):
    return await user_repo.get_users(group_id)

async def ensure_default_users():
    return await user_repo.ensure_default_admin_user()
