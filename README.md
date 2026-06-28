# Backend Working Task — Stantech

This is a small multi-tenant support-ticket API (FastAPI + SQLAlchemy + SQLite).
Each request identifies its tenant via the `X-Tenant-Id` header.

## Setup
```
pip install -r requirements.txt
python app.py          # seeds the database and starts the server
```
Then open http://localhost:8000/docs to try the existing endpoints.

## Your task
1. Add an endpoint to **reassign a ticket to a different agent**:
   `PATCH /tickets/{ticket_id}/assign` with a body like `{"agent_id": <int>}`.
   It should update the ticket's assigned agent and return the updated ticket.

2. Treat this as **production code that you will own and be on call for.**
   If anything in the existing service concerns you while you work on it,
   address it and note briefly why.

## How to work
- Use Claude (or whatever AI tooling you normally use) exactly as you would on the job.
- Submit **two** things:
  1. Your final code.
  2. The **complete, unedited** Claude conversation(s) you used to get there.
- Timebox it to roughly **45–60 minutes**. Polish matters less than judgement.

We're not measuring how much you produce. We're measuring how you think.

## Heads-up from the team
A few customers with large ticket volumes have mentioned the list view feels
sluggish lately. Nothing formally reported — just context as you work.
