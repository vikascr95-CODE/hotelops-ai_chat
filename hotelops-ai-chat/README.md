# HotelOps AI Chat

A standalone AI hotel receptionist and operations chat built with Python, FastAPI, SQLite, and a browser-based interface.

## Features

- AI receptionist using the OpenAI Responses API
- Persistent conversations and messages
- Multi-request task extraction and department routing
- Task tracking API with status updates
- SQLite database created automatically
- Demo fallback when no API key is configured (keyword-based; not full AI)

## Requirements

- Python 3.10+
- An OpenAI API key for real AI responses

## Windows setup (VS Code terminal / PowerShell)

```powershell
cd hotelops-ai-chat
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Open `.env`, replace `your_api_key_here` with your API key, and save it. Never share or commit `.env`.

Run:

```powershell
uvicorn main:app --reload
```

Open http://127.0.0.1:8000

API documentation: http://127.0.0.1:8000/docs

## Useful API routes

- `GET /health` - service status
- `POST /api/chat` - send a guest message
- `GET /api/conversations` - list conversations
- `GET /api/conversations/{id}/messages` - conversation history
- `GET /api/tasks` - list tasks
- `PATCH /api/tasks/{task_id}/status` - update a task status

Example chat request:

```json
{
  "message": "I am in room 305. My AC is not working and I need two extra towels.",
  "guest_name": "Guest",
  "room_number": "305"
}
```

Expected behavior with AI configured: two separate tasks, one for Maintenance and one for Housekeeping. Task IDs returned by the API confirm that the records were saved.

## Important limitations

This is a local development starter, not a production hotel deployment. It does not yet include user login, employee RBAC, property/tenant isolation, WhatsApp/voice channels, real reservation-system integration, notification delivery, payment processing, or emergency dispatch. Add authentication, authorization, rate limiting, audit trails, privacy controls, backups, and human approval workflows before exposing it publicly.

When `OPENAI_API_KEY` is absent, a small keyword-based demo fallback is used. It is not an AI model and may miss requests.
