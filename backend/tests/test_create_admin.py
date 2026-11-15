"""scripts.create_admin and scripts.send_test_email: server setup commands."""
import pytest

from scripts.create_admin import main

API = "/api/v1"


def _login(client, email, password):
    return client.post(f"{API}/auth/login", json={"email": email, "password": password})


def test_create_admin_and_sign_in(client, monkeypatch, capsys):
    monkeypatch.setenv("NEXA_ADMIN_PASSWORD", "Start12345")
    assert main(["--email", " Boss@School.KZ ", "--name", "Главный Админ"]) == 0
    assert "boss@school.kz" in capsys.readouterr().out
    r = _login(client, "boss@school.kz", "Start12345")
    assert r.status_code == 200
    me = client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"}).json()
    assert me["role"] == "admin" and me["full_name"] == "Главный Админ"


def test_refuses_duplicates_weak_passwords_and_missing_name(client, monkeypatch):
    monkeypatch.setenv("NEXA_ADMIN_PASSWORD", "Start12345")
    main(["--email", "boss@school.kz", "--name", "Админ"])
    with pytest.raises(SystemExit, match="уже существует"):
        main(["--email", "BOSS@school.kz", "--name", "Другой"])
    with pytest.raises(SystemExit, match="имя"):
        main(["--email", "second@school.kz"])
    with pytest.raises(SystemExit, match="e-mail"):
        main(["--email", "not-an-email", "--name", "X"])
    monkeypatch.setenv("NEXA_ADMIN_PASSWORD", "short")
    with pytest.raises(SystemExit, match="8"):
        main(["--email", "second@school.kz", "--name", "Второй"])


def test_reset_password_signs_out_old_sessions(client, monkeypatch):
    monkeypatch.setenv("NEXA_ADMIN_PASSWORD", "Start12345")
    main(["--email", "boss@school.kz", "--name", "Админ"])
    old = _login(client, "boss@school.kz", "Start12345").json()["access_token"]

    monkeypatch.setenv("NEXA_ADMIN_PASSWORD", "Changed12345")
    main(["--email", "boss@school.kz", "--reset-password"])
    assert _login(client, "boss@school.kz", "Start12345").status_code == 401
    assert _login(client, "boss@school.kz", "Changed12345").status_code == 200
    assert client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {old}"}).status_code == 401
    # only administrators can be reset this way
    with pytest.raises(SystemExit, match="не найден"):
        main(["--email", "nobody@school.kz", "--reset-password"])


def test_send_test_email_reports_problems(monkeypatch, capsys):
    from app.core.config import settings
    from scripts.send_test_email import main as send_main

    monkeypatch.setattr(settings, "EMAIL_BACKEND", "console")
    assert send_main(["--to", "x@example.com"]) == 1
    assert "EMAIL_BACKEND=console" in capsys.readouterr().out
    # SMTP configured but unreachable: the real error is shown, not swallowed
    monkeypatch.setattr(settings, "EMAIL_BACKEND", "smtp")
    monkeypatch.setattr(settings, "SMTP_HOST", "127.0.0.1")
    monkeypatch.setattr(settings, "SMTP_PORT", 9)
    monkeypatch.setattr(settings, "SMTP_TIMEOUT", 2)
    assert send_main(["--to", "x@example.com"]) == 1
    assert "FAILED" in capsys.readouterr().out
