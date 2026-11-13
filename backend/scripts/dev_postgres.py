"""Start a local PostgreSQL for development without installing it system-wide.

Uses the `pgserver` pip package (bundled PostgreSQL 16 binaries).
    pip install pgserver
    python -m scripts.dev_postgres            # prints the DATABASE_URL
Production / normal setups should use a regular PostgreSQL server instead.

Also creates `nexa_readonly`, a SELECT-only role used by the Postgres MCP
server configured in `.mcp.json`.
"""
from pathlib import Path

import pgserver
import psycopg

DATA_DIR = Path(__file__).resolve().parents[2] / ".devdata" / "pg"
READONLY_ROLE = "nexa_readonly"


def ensure_readonly_role(app_db_uri: str) -> None:
    with psycopg.connect(app_db_uri, autocommit=True) as conn:
        if not conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (READONLY_ROLE,)).fetchone():
            conn.execute(f"CREATE ROLE {READONLY_ROLE} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE")
        conn.execute(f"ALTER ROLE {READONLY_ROLE} SET default_transaction_read_only = on")
        conn.execute(f"GRANT CONNECT ON DATABASE english_lms TO {READONLY_ROLE}")
        conn.execute(f"GRANT USAGE ON SCHEMA public TO {READONLY_ROLE}")
        conn.execute(f"GRANT SELECT ON ALL TABLES IN SCHEMA public TO {READONLY_ROLE}")
        conn.execute(
            f"ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT SELECT ON TABLES TO {READONLY_ROLE}"
        )


if __name__ == "__main__":
    DATA_DIR.parent.mkdir(parents=True, exist_ok=True)
    srv = pgserver.get_server(str(DATA_DIR), cleanup_mode=None)
    for db in ("english_lms", "english_lms_test"):
        exists = srv.psql(f"SELECT 1 FROM pg_database WHERE datname = '{db}';")
        if "1 row" not in exists:
            srv.psql(f"CREATE DATABASE {db};")
    uri = srv.get_uri().rsplit("/", 1)[0] + "/english_lms"
    ensure_readonly_role(uri)
    print("PostgreSQL is running.")
    print("DATABASE_URL=" + uri.replace("postgresql://", "postgresql+psycopg://"))
    print(f"Read-only role for MCP: {READONLY_ROLE}")
