---
name: project-conventions
description: Conventions of the NEXA LMS codebase (FastAPI + React). Use whenever adding or changing an API endpoint, a model, a page, a dialog or any UI text in this project.
user-invocable: false
---

# NEXA LMS conventions

## Backend (FastAPI)
- **Auth & roles**: use the dependencies in `app/api/deps.py` — `CurrentUser`, `CurrentTeacher`, `CurrentStudent`, `AdminUser`. Never trust ids from the client.
- **Ownership**: load teacher-scoped objects with `get_owned_student`, `get_owned_students`, `get_owned_group`, `resolve_recipients` or a `_load`/`_get_owned_*` helper that checks `teacher_id`. Foreign objects raise `NotFound` (404) so their existence is not revealed. Student endpoints (`/me/...`) filter by `student.id`.
- **Errors**: raise `BadRequest` / `NotFound` / `Forbidden` / `Conflict` from `app/core/exceptions.py` with a short Russian message — the frontend shows `detail` directly.
- **Validation**: in Pydantic schemas (`app/schemas/`), messages in Russian (`ValueError("...")`).
- **Business logic** goes into `app/services/`, reusable queries into `app/repositories/`. Endpoints stay thin.
- **Notifications**: `services.notification_service.notify(db, user_ids, NotificationType.X, title, body, link)` inside the transaction; real-time delivery happens automatically on commit (pg_notify hook).
- **E-mail**: build the link (e.g. `account_service.invite_link`), commit, then `background.add_task(email_service.<template>, ...)`. In DEBUG return the link as `dev_*_url`.
- **Sessions**: incrementing `user.token_version` signs the user out everywhere and closes their SSE streams.
- **Schema change** → migration via the `create-migration` skill.
- **Tests**: add/extend a file in `backend/tests/` using the `school` fixture (teacher A with s1, s2; teacher B with s3; auth headers `ha`, `hb`, `h1`, `h2`, `h3`). Always test the "other teacher gets 404" case for new teacher endpoints.

## Frontend (React)
- Types in `src/types/api.ts` mirror the Pydantic response models exactly; API calls live only in `src/services/api.ts`.
- Data fetching with TanStack Query; after mutations invalidate the affected keys (`["students"]`, `["lessons"]`, `["dashboard"]`, ...). Errors → `toast.error(errorMessage(e))`; success → `toast.success(...)`.
- Every visible string goes through `useI18n()` and must be added to both `src/i18n/ru.ts` and `src/i18n/en.ts`.
- Use the UI kit (`src/components/ui/*`) and common blocks (`PageHeader`, `EmptyState`, `ErrorState`, `StatCard`, `Field`, skeletons from `src/components/common`). Destructive actions use `ConfirmDialog`.
- Loading states use skeletons, never a blank page. No dead buttons: every control calls a real API.
- Layout must work at 375px without horizontal scroll: tables live inside `Card` with their own overflow, single-column grids use `grid` (global `minmax(0,1fr)` rule) or `grid-cols-1`.
- Colors only via tokens (`accent`, `primary`, `success`, `warning`, `danger`, `secondary`, `border`).

## Definition of done
1. `cd backend && .venv/Scripts/python -m pyflakes app tests scripts` is clean.
2. `cd backend && .venv/Scripts/python -m pytest -q` passes.
3. `cd frontend && npx tsc -b --noEmit` passes.
4. The feature was clicked through in the browser (desktop and 375px).
5. `README.md` updated if behaviour, setup or API changed.
