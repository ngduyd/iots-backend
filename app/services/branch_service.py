from app.repositories import branch_repo, alert_repo

async def get_branches(group_id: int = None):
    return await branch_repo.get_branches(group_id)

async def get_branch(branch_id: int, group_id: int = None):
    return await branch_repo.get_branch(branch_id, group_id)

async def create_branch(group_id: int, name: str, thresholds: dict = None):
    return await branch_repo.create_branch(group_id, name, thresholds)

async def update_branch(branch_id: int, group_id: int, name: str, thresholds: dict = None):
    return await branch_repo.update_branch(branch_id, group_id, name, thresholds)

async def delete_branch(branch_id: int):
    return await branch_repo.delete_branch(branch_id)

async def get_groups():
    return await branch_repo.get_groups()

async def get_group(group_id: int):
    return await branch_repo.get_group(group_id)

async def create_group(name: str):
    return await branch_repo.create_group(name)

async def update_group(group_id: int, name: str):
    return await branch_repo.update_group(group_id, name)

async def delete_group(group_id: int):
    return await branch_repo.delete_group(group_id)

async def get_all_branch_thresholds():
    return await branch_repo.get_all_branch_thresholds()

async def update_branch_thresholds(branch_id: int, thresholds: dict):
    return await branch_repo.update_branch_thresholds(branch_id, thresholds)

async def get_alerts_by_branch(branch_id: int, limit: int = None, unread_only: bool = False):
    return await alert_repo.get_alerts_by_branch(branch_id, limit, unread_only)

async def mark_alert_as_read(alert_id: int):
    return await alert_repo.mark_alert_as_read_db(alert_id)
