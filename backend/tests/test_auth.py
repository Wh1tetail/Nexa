from conftest import PASSWORD, login, make_user

from app.models.enums import UserRole

API = "/api/v1"


def test_login_me_refresh_logout(client):
    make_user(UserRole.TEACHER, "t@test.io", name="T")
    r = client.post(f"{API}/auth/login", json={"email": "T@test.io", "password": PASSWORD})
    assert r.status_code == 200
    tokens = r.json()
    h = {"Authorization": f"Bearer {tokens['access_token']}"}
    me = client.get(f"{API}/auth/me", headers=h).json()
    assert me["role"] == "teacher" and me["teacher_id"]

    r = client.post(f"{API}/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 200
    # access token cannot be used as refresh token
    assert client.post(f"{API}/auth/refresh", json={"refresh_token": tokens["access_token"]}).status_code == 401

    assert client.post(f"{API}/auth/logout", headers=h).status_code == 200
    # all tokens revoked after logout
    assert client.get(f"{API}/auth/me", headers=h).status_code == 401
    assert client.post(f"{API}/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code == 401


def test_wrong_password_and_unauthenticated(client):
    make_user(UserRole.STUDENT, "s@test.io")
    r = client.post(f"{API}/auth/login", json={"email": "s@test.io", "password": "nope"})
    assert r.status_code == 401
    assert client.get(f"{API}/dashboard/student").status_code == 401


def test_password_reset_flow(client):
    make_user(UserRole.STUDENT, "s@test.io")
    r = client.post(f"{API}/auth/forgot-password", json={"email": "s@test.io"})
    url = r.json()["dev_reset_url"]
    token = url.split("token=")[1]
    # unknown email -> same generic answer, no link
    r2 = client.post(f"{API}/auth/forgot-password", json={"email": "ghost@test.io"})
    assert r2.json()["dev_reset_url"] is None
    assert client.post(f"{API}/auth/reset-password", json={"token": token, "new_password": "short"}).status_code == 422
    assert client.post(f"{API}/auth/reset-password", json={"token": token, "new_password": "NewPass123"}).status_code == 200
    # token is single-use
    assert client.post(f"{API}/auth/reset-password", json={"token": token, "new_password": "NewPass123"}).status_code == 400
    assert client.post(f"{API}/auth/login", json={"email": "s@test.io", "password": "NewPass123"}).status_code == 200


def test_roles_are_separated(client, school):
    assert client.get(f"{API}/students", headers=school["h1"]).status_code == 403
    assert client.get(f"{API}/dashboard/student", headers=school["ha"]).status_code == 403
    assert client.get(f"{API}/dashboard/teacher", headers=school["ha"]).status_code == 200
    assert client.get(f"{API}/admin/teachers", headers=school["ha"]).status_code == 403


def test_brute_force_limited(client):
    make_user(UserRole.STUDENT, "s@test.io")
    codes = [
        client.post(f"{API}/auth/login", json={"email": "s@test.io", "password": "bad"}).status_code
        for _ in range(11)
    ]
    assert codes[-1] == 429


def test_admin_creates_accounts(client):
    make_user(UserRole.ADMIN, "admin@test.io")
    h = login(client, "admin@test.io")
    t = client.post(f"{API}/admin/teachers", headers=h,
                    json={"email": "new.t@test.io", "full_name": "New T", "password": "Teacher123"})
    assert t.status_code == 201
    s = client.post(f"{API}/admin/students", headers=h, json={
        "email": "new.s@test.io", "full_name": "New S", "password": "Student123", "teacher_id": t.json()["id"]})
    assert s.status_code == 201
    assert s.json()["teacher_name"] == "New T"
    dup = client.post(f"{API}/admin/students", headers=h,
                      json={"email": "NEW.S@test.io", "full_name": "Dup", "password": "Student123"})
    assert dup.status_code == 409
