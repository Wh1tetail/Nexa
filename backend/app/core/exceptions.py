from fastapi import HTTPException, status


class NotFound(HTTPException):
    def __init__(self, detail: str = "Не найдено") -> None:
        super().__init__(status.HTTP_404_NOT_FOUND, detail)


class Forbidden(HTTPException):
    def __init__(self, detail: str = "Недостаточно прав") -> None:
        super().__init__(status.HTTP_403_FORBIDDEN, detail)


class BadRequest(HTTPException):
    def __init__(self, detail: str) -> None:
        super().__init__(status.HTTP_400_BAD_REQUEST, detail)


class Conflict(HTTPException):
    def __init__(self, detail: str) -> None:
        super().__init__(status.HTTP_409_CONFLICT, detail)


class Unauthorized(HTTPException):
    def __init__(self, detail: str = "Требуется авторизация") -> None:
        super().__init__(
            status.HTTP_401_UNAUTHORIZED, detail, headers={"WWW-Authenticate": "Bearer"}
        )
