# HotelOps AI

A local hotel guest-concierge and staff-operations starter built with FastAPI, SQLite, and the OpenAI Responses API.

## Included features
- Guest-facing AI chat with conversation history
- Multi-request extraction and routing to hotel departments
- Persistent SQLite task records and unique request IDs
- Staff operations dashboard at `/staff`
- Live request counts and department workload
- Search and filters by status, department, and priority
- Assign staff names and update task status
- Statuses: Pending, Assigned, In Progress, Completed, Escalated, Cancelled
- Automatic database migration for existing local databases
- Demo keyword fallback if no OpenAI API key is configured

## Windows setup (VS Code / PowerShell)
```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```
Edit `.env` and add your own OpenAI API key. Never share or commit this file.

Start the server:
```powershell
uvicorn main:app --reload
``

Open:
- Guest chat: http://127.0.0.1:8000
- Staff dashboard: http://127.0.0.1:8000/staff
- API documentation: http://127.0.0.1:8000/docs
- Health check: http://127.0.0.1:8000/health

## Staff workflow
1. A guest sends a request in the chat.
2. The AI identifies actionable requests and routes each to a department.
3. The backend records each request in SQLite with a unique `HOT-XXXXXXXX` ID and Pending status.
4. Staff open `/staff`, search/filter requests, enter an assignee, and save a new status.
5. Dashboard counts and department workload are recalculated from the database.

## API routes
- `POST /api/chat` — create guest conversation messages and task records
- `GET /api/tasks` — list/filter requests
- `GET /api/dashboard/summary` — dashboard counts and department totals
- `PATCH /api/tasks/{task_id}/status` — update task status
- `PATCH /api/tasks/{task_id}/assignment` — assign a staff member
- `GET /api/conversations` — list conversations
- `GET /api/conversations/{id}/messages` — retrieve conversation history

## Important
This is a functional local-development prototype, not a production hotel deployment. The staff dashboard currently has no login or role-based access control. Before using real guest data or exposing it to the internet, add authentication, staff permissions, property isolation, audit logs, backups, rate limits, privacy/security review, and real integrations. It does not connect to a PMS, WhatsApp, payment gateway, email/SMS notifications, or emergency dispatch. Human staff must verify and complete real-world guest requests.

If the API key is absent, the keyword fallback is a limited demo classifier, not a real AI model. ChatGPT subscription and API billing are separate.
