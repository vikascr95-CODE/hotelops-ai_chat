import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAI
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
DB_PATH = BASE_DIR / "hotelops_chat.db"
MODEL = os.getenv("OPENAI_MODEL", "gpt-5.5")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY")) if os.getenv("OPENAI_API_KEY") else None

app = FastAPI(title="HotelOps AI", version="1.1.0", description="AI guest concierge and hotel staff operations")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

DEPARTMENTS = ["Housekeeping", "Maintenance", "Reservations", "Room Service", "Front Office", "Concierge", "Accounts", "Security", "Other"]
PRIORITIES = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
STATUSES = ["PENDING", "ASSIGNED", "IN_PROGRESS", "COMPLETED", "CANCELLED", "ESCALATED"]

SCHEMA = {
    "type": "object",
    "properties": {
        "reply": {"type": "string"},
        "needs_human": {"type": "boolean"},
        "tasks": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "title": {"type": "string"}, "description": {"type": "string"},
                "department": {"type": "string", "enum": DEPARTMENTS},
                "room_number": {"type": ["string", "null"]},
                "priority": {"type": "string", "enum": PRIORITIES}
            },
            "required": ["title", "description", "department", "room_number", "priority"],
            "additionalProperties": False
        }}
    },
    "required": ["reply", "needs_human", "tasks"],
    "additionalProperties": False
}

SYSTEM_PROMPT = """
You are HotelOps AI, a courteous hotel receptionist and operations assistant.
Understand the guest's message and respond naturally.
Create one separate task for EACH actionable request. A message can create multiple tasks
for different departments. Do not create a task for a question that needs only an answer.
Departments: Housekeeping, Maintenance, Reservations, Room Service, Front Office,
Concierge, Accounts, Security, Other.
Priorities: LOW, MEDIUM, HIGH, CRITICAL. Use CRITICAL only for immediate safety or
serious emergencies; never claim emergency services have been contacted.
Extract a room number only when explicitly provided. If key details are missing, ask
a concise follow-up and do not invent them. Do not invent hotel policies, prices,
availability, booking changes, refunds, or completed work.
For financial actions, cancellations with financial impact, sensitive guest changes,
and security/emergency matters, set needs_human=true and explain that staff must review.
Task creation means a request has been recorded, NOT that the department has completed it.
Return only the required structured data.
"""

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = None
    guest_name: str | None = Field(default=None, max_length=120)
    room_number: str | None = Field(default=None, max_length=30)

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY, guest_name TEXT, room_number TEXT,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id TEXT NOT NULL,
            role TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT NOT NULL,
            FOREIGN KEY(conversation_id) REFERENCES conversations(id)
        );
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL,
            title TEXT NOT NULL, description TEXT NOT NULL,
            department TEXT NOT NULL, room_number TEXT,
            priority TEXT NOT NULL, status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(conversation_id) REFERENCES conversations(id)
        );
        """)
        # Safe, repeatable migration for databases created by earlier versions.
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(tasks)").fetchall()}
        if "updated_at" not in columns:
            conn.execute("ALTER TABLE tasks ADD COLUMN updated_at TEXT")
            conn.execute("UPDATE tasks SET updated_at=created_at WHERE updated_at IS NULL")
        if "assigned_to" not in columns:
            conn.execute("ALTER TABLE tasks ADD COLUMN assigned_to TEXT")

@app.on_event("startup")
def startup():
    init_db()

@app.get("/")
def home():
    return FileResponse(BASE_DIR / "static" / "index.html")

@app.get("/staff")
def staff_dashboard():
    return FileResponse(BASE_DIR / "static" / "staff.html")

@app.get("/health")
def health():
    return {"status": "ok", "ai_configured": client is not None, "version": app.version}

def fallback_understanding(message: str, room_number: str | None) -> dict[str, Any]:
    lower = message.lower()
    tasks = []
    rules = [
        (["towel", "towels", "linen", "pillow", "blanket", "clean", "housekeeping"], "Housekeeping", "Guest requested housekeeping assistance"),
        (["ac", "air conditioner", "plumbing", "leak", "light", "tv", "wifi", "broken", "not working"], "Maintenance", "Guest reported a maintenance issue"),
        (["food", "order", "meal", "water", "room service"], "Room Service", "Guest requested room service"),
        (["book", "reservation", "check in", "check-in", "checkout", "check-out"], "Reservations", "Guest has a reservation-related request"),
        (["taxi", "cab", "airport", "tour", "restaurant nearby"], "Concierge", "Guest requested concierge assistance"),
        (["bill", "invoice", "refund", "payment"], "Accounts", "Guest has an accounts-related request"),
        (["security", "unsafe", "theft", "emergency", "fire"], "Security", "Guest reported a security or safety concern"),
    ]
    for keywords, dept, default_title in rules:
        if any(k in lower for k in keywords):
            title = message.strip()[:100] if len(message.strip()) < 100 else default_title
            priority = "CRITICAL" if any(k in lower for k in ["fire", "emergency", "unsafe"]) else "MEDIUM"
            tasks.append({"title": title, "description": message, "department": dept, "room_number": room_number, "priority": priority})
    reply = (f"I've identified {len(tasks)} request(s) and recorded them for the relevant teams. Staff will need to review and action them."
             if tasks else "Hello! I'm the HotelOps AI receptionist. How can I help with your stay today?")
    return {"reply": reply, "needs_human": any(t["department"] in ["Accounts", "Security"] for t in tasks), "tasks": tasks}

def ask_ai(message: str, history: list[dict], room_number: str | None) -> dict[str, Any]:
    if client is None:
        return fallback_understanding(message, room_number)
    context = [{"role": item["role"], "content": item["content"]} for item in history[-12:]]
    context.append({"role": "user", "content": message})
    try:
        response = client.responses.create(
            model=MODEL,
            instructions=SYSTEM_PROMPT + (f"\nVerified room number supplied by guest: {room_number}." if room_number else ""),
            input=context,
            text={"format": {"type": "json_schema", "name": "hotelops_chat_result", "strict": True, "schema": SCHEMA}},
        )
        data = json.loads(response.output_text)
        if not isinstance(data.get("tasks"), list) or not isinstance(data.get("reply"), str):
            raise ValueError("Unexpected AI response format")
        return data
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"AI service error. Check your API key, model access and connection. ({type(exc).__name__})")

@app.post("/api/chat")
def chat(payload: ChatRequest):
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")
    conversation_id = payload.conversation_id or str(uuid.uuid4())
    with db() as conn:
        existing = conn.execute("SELECT * FROM conversations WHERE id=?", (conversation_id,)).fetchone()
        if existing is None:
            conn.execute("INSERT INTO conversations(id,guest_name,room_number,created_at,updated_at) VALUES(?,?,?,?,?)",
                         (conversation_id, payload.guest_name, payload.room_number, now_iso(), now_iso()))
        else:
            payload.room_number = payload.room_number or existing["room_number"]
            payload.guest_name = payload.guest_name or existing["guest_name"]
            conn.execute("UPDATE conversations SET guest_name=?, room_number=?, updated_at=? WHERE id=?",
                         (payload.guest_name, payload.room_number, now_iso(), conversation_id))
        history = [dict(r) for r in conn.execute(
            "SELECT role,content FROM messages WHERE conversation_id=? ORDER BY id DESC LIMIT 12", (conversation_id,)
        ).fetchall()][::-1]
    result = ask_ai(message, history, payload.room_number)
    created_tasks = []
    with db() as conn:
        conn.execute("INSERT INTO messages(conversation_id,role,content,created_at) VALUES(?,?,?,?)",
                     (conversation_id, "user", message, now_iso()))
        for task in result["tasks"]:
            dept = task.get("department")
            if dept not in DEPARTMENTS:
                continue
            priority = task.get("priority") if task.get("priority") in PRIORITIES else "MEDIUM"
            task_id = "HOT-" + uuid.uuid4().hex[:8].upper()
            room = task.get("room_number") or payload.room_number
            stamp = now_iso()
            conn.execute("""INSERT INTO tasks
                (id,conversation_id,title,description,department,room_number,priority,status,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (task_id, conversation_id, task["title"][:160], task["description"][:1000],
                 dept, room, priority, "PENDING", stamp, stamp))
            created_tasks.append({"id": task_id, "title": task["title"], "department": dept,
                                  "room_number": room, "priority": priority, "status": "PENDING"})
        reply = result["reply"]
        if created_tasks:
            reply += "\n\nRequest ID(s): " + ", ".join(t["id"] for t in created_tasks)
        if result.get("needs_human"):
            reply += "\n\nA staff member must review this request before any sensitive action is taken."
        conn.execute("INSERT INTO messages(conversation_id,role,content,created_at) VALUES(?,?,?,?)",
                     (conversation_id, "assistant", reply, now_iso()))
        conn.execute("UPDATE conversations SET updated_at=? WHERE id=?", (now_iso(), conversation_id))
    return {"conversation_id": conversation_id, "reply": reply, "tasks": created_tasks,
            "ai_mode": "openai" if client else "demo-fallback"}

@app.get("/api/conversations")
def conversations():
    with db() as conn:
        rows = conn.execute("""SELECT c.id,c.guest_name,c.room_number,c.updated_at,
            (SELECT content FROM messages m WHERE m.conversation_id=c.id ORDER BY id DESC LIMIT 1) last_message
            FROM conversations c ORDER BY c.updated_at DESC LIMIT 100""").fetchall()
    return [dict(r) for r in rows]

@app.get("/api/conversations/{conversation_id}/messages")
def conversation_messages(conversation_id: str):
    with db() as conn:
        exists = conn.execute("SELECT id FROM conversations WHERE id=?", (conversation_id,)).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail="Conversation not found.")
        rows = conn.execute("SELECT role,content,created_at FROM messages WHERE conversation_id=? ORDER BY id",
                            (conversation_id,)).fetchall()
    return [dict(r) for r in rows]

@app.get("/api/tasks")
def tasks(status: str | None = None, department: str | None = None,
          priority: str | None = None, search: str | None = None):
    query = "SELECT * FROM tasks WHERE 1=1"
    args: list[Any] = []
    if status and status.upper() in STATUSES:
        query += " AND status=?"; args.append(status.upper())
    if department and department in DEPARTMENTS:
        query += " AND department=?"; args.append(department)
    if priority and priority.upper() in PRIORITIES:
        query += " AND priority=?"; args.append(priority.upper())
    if search:
        term = f"%{search.strip()}%"
        query += " AND (id LIKE ? OR title LIKE ? OR description LIKE ? OR room_number LIKE ?)"
        args.extend([term, term, term, term])
    query += " ORDER BY CASE priority WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2 WHEN 'MEDIUM' THEN 3 ELSE 4 END, created_at DESC LIMIT 500"
    with db() as conn:
        rows = conn.execute(query, args).fetchall()
    return [dict(r) for r in rows]

@app.get("/api/dashboard/summary")
def dashboard_summary():
    with db() as conn:
        rows = conn.execute("SELECT status, COUNT(*) count FROM tasks GROUP BY status").fetchall()
        by_department = conn.execute("SELECT department, COUNT(*) count FROM tasks GROUP BY department ORDER BY count DESC").fetchall()
        total = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        recent = conn.execute("SELECT id,title,department,room_number,priority,status,created_at FROM tasks ORDER BY created_at DESC LIMIT 6").fetchall()
    counts = {status: 0 for status in STATUSES}
    counts.update({row["status"]: row["count"] for row in rows})
    return {"total": total, "pending": counts["PENDING"], "assigned": counts["ASSIGNED"],
            "in_progress": counts["IN_PROGRESS"], "completed": counts["COMPLETED"],
            "escalated": counts["ESCALATED"], "cancelled": counts["CANCELLED"],
            "by_department": [dict(r) for r in by_department], "recent": [dict(r) for r in recent]}

@app.patch("/api/tasks/{task_id}/status")
def update_task_status(task_id: str, payload: dict):
    status = str(payload.get("status", "")).upper()
    if status not in STATUSES:
        raise HTTPException(status_code=400, detail=f"Status must be one of: {', '.join(STATUSES)}")
    with db() as conn:
        cur = conn.execute("UPDATE tasks SET status=?, updated_at=? WHERE id=?", (status, now_iso(), task_id))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Task not found.")
        row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    return dict(row)

@app.patch("/api/tasks/{task_id}/assignment")
def assign_task(task_id: str, payload: dict):
    assignee = str(payload.get("assigned_to", "")).strip()[:120] or None
    with db() as conn:
        cur = conn.execute("UPDATE tasks SET assigned_to=?, updated_at=? WHERE id=?", (assignee, now_iso(), task_id))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Task not found.")
        row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    return dict(row)
