import json
import uuid
from datetime import datetime, timezone
import sqlite3

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

def enqueue_task_notification(conn: sqlite3.Connection, task: dict) -> None:
    event_key = f"task-created:{task['id']}"
    payload = json.dumps({"task_id": task["id"], "department": task["department"], "title": task["title"]})
    conn.execute(
        """INSERT OR IGNORE INTO outbox_events
        (event_key,event_type,payload,status,attempts,created_at)
        VALUES(?,?,?,'PENDING',0,?)""",
        (event_key, "TASK_CREATED", payload, utc_now()),
    )

def process_outbox(conn: sqlite3.Connection, limit: int = 100) -> int:
    """Idempotently materialize pending task-created events as in-app notifications."""
    rows = conn.execute(
        "SELECT id,event_key,payload FROM outbox_events WHERE status='PENDING' ORDER BY id LIMIT ?",
        (limit,),
    ).fetchall()
    processed = 0
    for row in rows:
        data = json.loads(row["payload"])
        conn.execute(
            """INSERT OR IGNORE INTO notifications
            (id,event_key,task_id,department,title,message,is_read,created_at)
            VALUES(?,?,?,?,?,?,0,?)""",
            (str(uuid.uuid4()), row["event_key"], data["task_id"], data["department"],
             "New guest request", data["title"], utc_now()),
        )
        conn.execute(
            "UPDATE outbox_events SET status='PROCESSED',processed_at=? WHERE id=?",
            (utc_now(), row["id"]),
        )
        processed += 1
    return processed
