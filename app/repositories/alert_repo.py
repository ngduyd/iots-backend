from app.db.session import fetch, fetchrow

async def create_alert(branch_id, message, level):
    return await fetchrow(
        "INSERT INTO alerts (branch_id, message, level) VALUES ($1, $2, $3) RETURNING alert_id, branch_id, message, level, is_read, created_at;",
        branch_id, message, level,
    )

async def get_alerts_by_branch(branch_id, limit=None, unread_only=False):
    query = "SELECT alert_id, branch_id, message, level, is_read, created_at FROM alerts WHERE branch_id = $1"
    if unread_only:
        query += " AND is_read = FALSE"
    query += " ORDER BY created_at DESC"
    if limit is not None:
        query += f" LIMIT {int(limit)}"
    return await fetch(query + ";", branch_id)

async def mark_alert_as_read_db(alert_id):
    return await fetchrow(
        "UPDATE alerts SET is_read = TRUE WHERE alert_id = $1 RETURNING alert_id, is_read;",
        alert_id,
    )
