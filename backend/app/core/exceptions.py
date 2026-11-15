"""API errors. The message is a Russian template (the message id, see
app/core/i18n.py) plus optional values; it is translated into the request's
language when the response is built (exception handler in app/main.py)."""
from typing import Any

from fastapi import HTTPException, status


class AppError(HTTPException):
    def __init__(
        self, status_code: int, template: str, headers: dict[str, str] | None = None,
        code: str | None = None, **params: Any,
    ) -> None:
        self.template = template
        self.params = params
        self.code = code  # machine-readable reason for the frontend, e.g. "subscription_required"
        super().__init__(status_code, template.format(**params) if params else template, headers=headers)


class NotFound(AppError):
    def __init__(self, detail: str = "Не найдено", **params: Any) -> None:
        super().__init__(status.HTTP_404_NOT_FOUND, detail, **params)


class Forbidden(AppError):
    def __init__(self, detail: str = "Недостаточно прав", code: str | None = None, **params: Any) -> None:
        super().__init__(status.HTTP_403_FORBIDDEN, detail, code=code, **params)


class BadRequest(AppError):
    def __init__(self, detail: str, **params: Any) -> None:
        super().__init__(status.HTTP_400_BAD_REQUEST, detail, **params)


class Conflict(AppError):
    def __init__(self, detail: str, **params: Any) -> None:
        super().__init__(status.HTTP_409_CONFLICT, detail, **params)


class Unauthorized(AppError):
    def __init__(self, detail: str = "Требуется авторизация", **params: Any) -> None:
        super().__init__(status.HTTP_401_UNAUTHORIZED, detail, headers={"WWW-Authenticate": "Bearer"}, **params)
