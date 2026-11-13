---
name: create-migration
description: Create, review and apply an Alembic migration after changing SQLAlchemy models in backend/app/models.
disable-model-invocation: true
argument-hint: "<short description, e.g. 'add lesson room'>"
---

# Create an Alembic migration

Run from `backend/`. Description of the change: $ARGUMENTS

1. **Check the models compile**
   `.venv/Scripts/python -c "import app.models; print('ok')"`
2. **Make sure the database is reachable and up to date**
   `.venv/Scripts/alembic current` — it must show the latest revision (`alembic heads`). If PostgreSQL is not running: `.venv/Scripts/python -m scripts.dev_postgres`.
3. **Pick the next revision id**: list `alembic/versions/` — ids are sequential 4-digit numbers (`0001`, `0002`, ...). Use the next one.
4. **Generate**
   `.venv/Scripts/alembic revision --autogenerate -m "<description>" --rev-id <NNNN>`
5. **Review the generated file** in `alembic/versions/` before applying:
   - Only the intended tables/columns changed (no accidental drops).
   - New NOT NULL columns on existing tables have a `server_default` or a data backfill step, otherwise `upgrade` fails on non-empty tables.
   - Enums are `VARCHAR + CHECK` (the `str_enum()` helper) — never `postgresql.ENUM`.
   - Constraint/index names follow the naming convention in `app/core/database.py` (`ix_`, `uq_`, `ck_`, `fk_`).
   - `downgrade()` reverses `upgrade()`.
   - Never edit a migration that has already been applied/committed — create a new one.
6. **Apply** `.venv/Scripts/alembic upgrade head`
7. **Check round-trip** `.venv/Scripts/alembic downgrade -1 && .venv/Scripts/alembic upgrade head`
8. **Run tests** `.venv/Scripts/python -m pytest -q` — the test database is rebuilt from migrations, so this also proves the migration works on an empty DB.
9. If the API changed, follow the `project-conventions` skill (schemas → `types/api.ts` → `services/api.ts` → tests) and mention the migration in `README.md`.
