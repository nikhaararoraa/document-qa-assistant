# Backend

FastAPI service for the Document Q&A Assistant — SEC Filings.

## Setup

```bash
cd backend
uv sync
cp .env.example .env   # fill in Supabase / OpenAI values
```

## Run

Always run from `backend/` (not from inside `app/`) so `from app...` imports resolve.

```bash
uv run python -m uvicorn app.main:app --reload
```

> `uv run uvicorn app.main:app --reload` (without `python -m`) is the more common form and works on most machines — use `python -m uvicorn` if your machine blocks spawning `uvicorn.exe` directly (e.g. an Application Control / AppLocker policy).

Server runs at `http://127.0.0.1:8000`.

- `GET /health` — health check, returns `{"status": "ok"}`
- `GET /docs` — interactive Swagger UI, lists every live route

## Config

All environment variables are read through `app/config.py` (`pydantic-settings`, loads `.env`). The app fails fast at startup if a required variable is missing — never read `os.environ` directly elsewhere.

## Tests

```bash
uv run pytest -m "not integration"
```
