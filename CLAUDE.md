# Lingua LMS — notes for Claude

Online English school LMS. Russian UI by default (English supported). Full docs: `README.md`.

## Layout
- `backend/` — FastAPI + SQLAlchemy 2 + Alembic + PostgreSQL. Layers: `core/` (settings, db, security), `models/`, `schemas/` (Pydantic, server-side validation), `repositories/`, `services/` (business logic), `api/v1/endpoints/`, `storage/`, `middleware/`.
- `frontend/` — React 18 + TS + Vite + Tailwind + shadcn-style components (`src/components/ui`), TanStack Query, react-hook-form + Zod.

## Commands (Windows, Git Bash)
- Dev Postgres (no system install): `cd backend && .venv/Scripts/python -m scripts.dev_postgres`
- Migrations: `cd backend && .venv/Scripts/alembic upgrade head`
- Backend: `cd backend && .venv/Scripts/python -m uvicorn app.main:app --port 8000` (or the `backend` entry in `.claude/launch.json`)
- Frontend: `cd frontend && npm run dev` (Vite proxies `/api` to :8000)
- Tests (real PostgreSQL, ~3 min): `cd backend && .venv/Scripts/python -m pytest -q`
- Lint: `cd backend && .venv/Scripts/python -m pyflakes app tests scripts`
- Types/build: `cd frontend && npx tsc -b --noEmit` / `npm run build`
- Demo data: `cd backend && .venv/Scripts/python -m scripts.seed --reset` (password `Demo12345` for all demo users)

## Rules that are easy to break
- Ownership: teacher endpoints load students/groups/lessons via `get_owned_*` in `app/api/deps.py`; foreign objects return **404**, not 403. Students only ever see their own data.
- Every API change touches four places: Pydantic schema → `frontend/src/types/api.ts` → `frontend/src/services/api.ts` → a test in `backend/tests/`.
- Every UI string goes into both `frontend/src/i18n/ru.ts` and `en.ts` (the `Dict` type enforces matching keys).
- Schema changes go through an Alembic migration (see the `create-migration` skill); never edit applied migrations.
- E-mail is sent only via `BackgroundTasks` + `services/email_service.py`.
- Bumping `users.token_version` revokes all sessions and closes open SSE streams (`services/realtime.py`).
- Main data lives in PostgreSQL; `localStorage` only holds the refresh token and UI preferences.
- No horizontal scroll at 375px; dialogs are bottom sheets on mobile.
- Never edit `backend/.env` (use `.env.example`) or lock files by hand — a hook blocks it.
