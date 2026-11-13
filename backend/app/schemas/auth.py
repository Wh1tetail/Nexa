from pydantic import BaseModel, EmailStr, Field, field_validator


def _password_rules(v: str) -> str:
    if len(v) < 8:
        raise ValueError("Пароль должен содержать минимум 8 символов")
    if not any(c.isdigit() for c in v) or not any(c.isalpha() for c in v):
        raise ValueError("Пароль должен содержать буквы и цифры")
    return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    detail: str
    # Only populated when DEBUG=true (no e-mail provider configured in dev).
    dev_reset_url: str | None = None


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=10)
    new_password: str = Field(max_length=128)

    _v = field_validator("new_password")(_password_rules)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(max_length=128)

    _v = field_validator("new_password")(_password_rules)


validate_password = _password_rules
