"""Create the first administrator on a real server (the demo seed is not for production).

    python -m scripts.create_admin --email admin@example.com --name "Имя Фамилия"

In Docker:

    docker compose exec backend python -m scripts.create_admin --email ... --name "..."

The password is asked twice (not shown, not saved in the shell history). For
automation it can come from the NEXA_ADMIN_PASSWORD environment variable.
--reset-password sets a new password for an existing administrator and signs
out all of their sessions.
"""
import argparse
import getpass
import os
import sys

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import User
from app.models.enums import UserRole
from app.schemas.auth import _password_rules


def _read_password() -> str:
    env = os.environ.get("NEXA_ADMIN_PASSWORD")
    if env:
        return env
    if not sys.stdin.isatty():
        raise SystemExit("Нет терминала: задайте пароль в NEXA_ADMIN_PASSWORD или запустите с `docker compose exec -it`")
    first = getpass.getpass("Пароль: ")
    if getpass.getpass("Пароль ещё раз: ") != first:
        raise SystemExit("Пароли не совпадают")
    return first


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create a NEXA administrator")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", help="full name (required for a new administrator)")
    parser.add_argument("--reset-password", action="store_true", help="new password for an existing administrator")
    args = parser.parse_args(argv)

    try:
        email = str(TypeAdapter(EmailStr).validate_python(args.email.strip())).lower()
    except ValidationError:
        raise SystemExit(f"Некорректный e-mail: {args.email}")

    with SessionLocal() as db:
        user = db.scalar(select(User).where(func.lower(User.email) == email))
        if user and not args.reset_password:
            raise SystemExit(f"Пользователь {email} уже существует (для нового пароля: --reset-password)")
        if args.reset_password and (user is None or user.role != UserRole.ADMIN):
            raise SystemExit(f"Администратор {email} не найден")
        if user is None and not (args.name and args.name.strip()):
            raise SystemExit("Укажите имя: --name \"Имя Фамилия\"")

        try:
            password = _password_rules(_read_password())
        except ValueError as e:
            raise SystemExit(str(e))

        if user:
            user.password_hash = hash_password(password)
            user.token_version += 1  # sign out everywhere
            action = "Пароль обновлён"
        else:
            db.add(User(email=email, password_hash=hash_password(password),
                        full_name=args.name.strip(), role=UserRole.ADMIN))
            action = "Администратор создан"
        db.commit()
    print(f"{action}: {email}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
