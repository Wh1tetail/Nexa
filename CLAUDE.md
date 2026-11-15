# NEXA LMS — notes for Claude

Online English school LMS. Russian UI by default (English supported). Full docs: `README.md`.

## Layout
- `backend/` — FastAPI + SQLAlchemy 2 + Alembic + PostgreSQL. Layers: `core/` (settings, db, security), `models/`, `schemas/` (Pydantic, server-side validation), `repositories/`, `services/` (business logic), `api/v1/endpoints/`, `storage/`, `middleware/`.
- `frontend/` — React 18 + TS + Vite + Tailwind + shadcn-style components (`src/components/ui`), TanStack Query, react-hook-form + Zod.

## Commands (Windows, Git Bash)
- Database: local PostgreSQL 18 Windows service (`postgresql-x64-18`, port 5432); main DB from `DATABASE_URL` in `backend/.env`, tests use `<db>_test`. Fallback without an install: `cd backend && .venv/Scripts/python -m scripts.dev_postgres` (port 4934)
- DB inspection: `postgres-dev` MCP server, read-only role `nexa_readonly`, URL in `NEXA_RO_DATABASE_URL` (`.claude/settings.local.json`, not in git)
- Migrations: `cd backend && .venv/Scripts/alembic upgrade head`
- Backend: `cd backend && .venv/Scripts/python -m uvicorn app.main:app --port 8000` (or the `backend` entry in `.claude/launch.json`)
- Frontend: `cd frontend && npm run dev` (Vite proxies `/api` to :8000)
- Tests (real PostgreSQL, ~4 min; wipe the `<db>_test` database each run): `cd backend && .venv/Scripts/python -m pytest -q`
- Lint: `cd backend && .venv/Scripts/python -m pyflakes app tests scripts`
- Dependencies: `backend/requirements.txt` = runtime only (goes into the Docker image); dev/CI tools in `requirements-dev.txt`
- CI: `.github/workflows/ci.yml` (backend tests on PostgreSQL 18, frontend build, docker compose smoke test). Production: `docker-compose.yml` + `.env` from `.env.production.example`. Docker is not installed locally — the compose stack is verified only in CI.
- Types/build: `cd frontend && npx tsc -b --noEmit` / `npm run build`
- Demo data: `cd backend && .venv/Scripts/python -m scripts.seed --reset` (password `Demo12345` for all demo users)
- Production server (README «Запуск на VPS с доменом»): `docker compose --profile https up -d --build` (Caddy HTTPS for `DOMAIN`, nginx bound to `HTTP_BIND=127.0.0.1`); first admin `python -m scripts.create_admin`, SMTP check `python -m scripts.send_test_email`; the `backup` service writes DB dumps + file archives to `BACKUP_DIR`. New backend settings must also be passed through `docker-compose.yml` and listed in `.env.production.example`.

## Rules that are easy to break
- Ownership: teacher endpoints load students/groups/lessons via `get_owned_*` in `app/api/deps.py`; foreign objects return **404**, not 403. Students only ever see their own data.
- Creating students, groups and lessons (and deleting groups/lessons, extending series) is admin-only: use `AdminForTeacher`; reading/editing uses `ActingTeacher` (teacher = own data, admin = teacher from `X-Teacher-Id`/`?teacher_id=`). Teachers may only change a lesson's topic, add students and mark attendance. Subscriptions: teachers only view them; create/edit/extend/use-lesson/freeze/delete are `AdminForTeacher` (frontend: `useCanManageSubscriptions`).
- Student lessons/homework/tests/attendance (and their files) require an active subscription: use `StudentWithAccess`, not `CurrentStudent` (403 `code: "subscription_required"`); checked live, so renewal reopens access.
- Every API change touches four places: Pydantic schema → `frontend/src/types/api.ts` → `frontend/src/services/api.ts` → a test in `backend/tests/`.
- Server texts (errors, ValueError, notifications) are Russian templates translated via `app/core/i18n.py` CATALOG: pass values as params (`BadRequest("Не более {n} файлов", n=5)`, `M(...)` for notifications) — never f-strings; a test fails if a text has no kk/en translation. E-mail templates take the recipient's `lang`.
- Every UI string goes into `frontend/src/i18n/ru.ts`, `en.ts` and `kk.ts` (the `Dict` type enforces matching keys). Kazakh dates are built in `utils/format.ts` (`formatInstant`) — browsers often lack Kazakh month names.
- Schema changes go through an Alembic migration (see the `create-migration` skill); never edit applied migrations.
- E-mail is sent only through `services/email_service.py`: from requests via `BackgroundTasks`; copies of notifications/chat messages only via the outbox worker (`services/email_outbox.py`) — never send those from a request.
- Bumping `users.token_version` revokes all sessions and closes open SSE streams (`services/realtime.py`). Other live events go through `realtime.publish(db, ...)` inside the transaction (delivered on commit), e.g. chat in `services/message_service.py`.
- Test attempts: a student may have several per test (`TestAttempt.number`); the latest is `attempts_of(...)[-1]`, the best (`best_attempt`) counts in analytics. Never delete attempts to allow a retake — add `test_assignments.extra_attempts`.
- Chat threads are keyed by `student_id` and exist only between a student and their CURRENT teacher; anything else is 404.
- Time: store UTC; anything "wall clock" (weekly series, texts for people, CSV) goes through `app/core/timezones.py` with the user's `users.timezone`. Frontend formats only via `utils/format.ts` (profile time zone), never raw `toLocaleString`/`setHours`.
- Main data lives in PostgreSQL; `localStorage` only holds the refresh token and UI preferences.
- No horizontal scroll at 375px; dialogs are bottom sheets on mobile.
- Never edit `backend/.env` (use `.env.example`) or lock files by hand — a hook blocks it.
