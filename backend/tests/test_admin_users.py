"""Administrator: edit any user (including e-mail), delete teachers and students."""
from datetime import UTC, datetime, timedelta

from conftest import PASSWORD

from app.core.database import SessionLocal
from app.models import Group, Lesson, StudentProfile, Subscription, TeacherProfile, User

API = "/api/v1"


def _user_id(email: str) -> int:
    with SessionLocal() as db:
        return db.query(User.id).filter(User.email == email).scalar()


def _login(client, email, password=PASSWORD):
    return client.post(f"{API}/auth/login", json={"email": email, "password": password})


# ---------- editing ----------

def test_admin_changes_name_email_phone_and_level(client, school):
    uid = _user_id("s1@test.io")
    r = client.patch(f"{API}/admin/users/{uid}", headers=school["adm"], json={
        "full_name": "Student Renamed", "email": "New.Address@Test.io", "phone": "+7 700 000 0000",
        "english_level": "B2"})
    assert r.status_code == 200, r.text
    out = r.json()
    assert (out["full_name"], out["email"], out["phone"], out["english_level"]) == (
        "Student Renamed", "new.address@test.io", "+7 700 000 0000", "B2")
    # the new address is the login now, the old one no longer works
    assert _login(client, "new.address@test.io").status_code == 200
    assert _login(client, "s1@test.io").status_code == 401
    # the teacher sees the change
    me = client.get(f"{API}/students/{school['s1'].id}", headers=school["ha"]).json()
    assert me["email"] == "new.address@test.io" and me["english_level"] == "B2"


def test_email_must_be_unique_and_valid(client, school):
    uid = _user_id("s1@test.io")
    r = client.patch(f"{API}/admin/users/{uid}", headers=school["adm"], json={"email": "S2@test.io"})
    assert r.status_code == 409
    assert client.patch(f"{API}/admin/users/{uid}", headers=school["adm"], json={"email": "nope"}).status_code == 422
    # same address in another case is not a conflict with itself
    assert client.patch(f"{API}/admin/users/{uid}", headers=school["adm"], json={"email": "S1@test.io"}).status_code == 200


def test_level_only_for_students_and_only_admin_edits(client, school):
    tid = _user_id("ta@test.io")
    r = client.patch(f"{API}/admin/users/{tid}", headers=school["adm"], json={"english_level": "C1"})
    assert r.status_code == 400
    # a teacher cannot use the admin endpoints
    assert client.patch(f"{API}/admin/users/{tid}", headers=school["ha"], json={"full_name": "X Y"}).status_code == 403
    assert client.delete(f"{API}/admin/users/{_user_id('s1@test.io')}", headers=school["ha"]).status_code == 403


# ---------- deleting a student ----------

def test_delete_student_removes_their_data(client, school):
    s1 = school["s1"].id
    uid = _user_id("s1@test.io")
    assert client.post(f"{API}/messages/threads/{s1}", headers=school["ha"], json={"body": "Hello"}).status_code == 201
    assert client.delete(f"{API}/admin/users/{uid}", headers=school["adm"]).status_code == 204
    with SessionLocal() as db:
        assert db.get(User, uid) is None
        assert db.get(StudentProfile, s1) is None
        assert db.query(Subscription).filter_by(student_id=s1).count() == 0
    assert client.get(f"{API}/auth/me", headers=school["h1"]).status_code == 401  # signed out
    assert client.get(f"{API}/students/{s1}", headers=school["ha"]).status_code == 404
    # the other students are untouched
    assert len(client.get(f"{API}/students", headers=school["ha"]).json()) == 1


# ---------- deleting a teacher ----------

def test_teacher_with_students_needs_a_new_teacher(client, school):
    uid = _user_id("ta@test.io")
    r = client.delete(f"{API}/admin/users/{uid}", headers=school["adm"])
    assert r.status_code == 400
    assert client.delete(f"{API}/admin/users/{uid}", headers=school["adm"],
                         params={"transfer_to": school["ta"].id}).status_code == 400  # not to themselves
    assert client.delete(f"{API}/admin/users/{uid}", headers=school["adm"],
                         params={"transfer_to": 999999}).status_code == 404
    with SessionLocal() as db:
        assert db.get(User, uid) is not None  # nothing happened


def test_delete_teacher_moves_students_with_subscriptions(client, school):
    ta, tb = school["ta"], school["tb"]
    start = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    client.post(f"{API}/groups", headers=school["aa"], json={"name": "Evening", "student_ids": [school["s1"].id]})
    client.post(f"{API}/lessons", headers=school["aa"], json={
        "title": "Grammar", "starts_at": start, "student_ids": [school["s1"].id]})

    uid = _user_id("ta@test.io")
    r = client.delete(f"{API}/admin/users/{uid}", headers=school["adm"], params={"transfer_to": tb.id})
    assert r.status_code == 204, r.text
    with SessionLocal() as db:
        assert db.get(TeacherProfile, ta.id) is None
        for s in (school["s1"], school["s2"]):
            student = db.get(StudentProfile, s.id)
            assert student.teacher_id == tb.id and student.groups == []
            sub = db.query(Subscription).filter_by(student_id=s.id).one()  # paid package kept
            assert sub.teacher_id == tb.id
        # the old teacher's own groups and lessons are gone
        assert db.query(Group).filter_by(teacher_id=ta.id).count() == 0
        assert db.query(Lesson).filter_by(teacher_id=ta.id).count() == 0
    # teacher B now sees all three students; their access to lessons is unchanged
    assert len(client.get(f"{API}/students", headers=school["hb"]).json()) == 3
    assert client.get(f"{API}/me/homework", headers=school["h1"]).status_code == 200
    assert client.get(f"{API}/auth/me", headers=school["ha"]).status_code == 401


def test_subscription_left_from_an_earlier_transfer_follows_the_student(client, school):
    tb = school["tb"]
    # s1 moved to B earlier: the subscription still points to A
    client.post(f"{API}/admin/students/{school['s1'].id}/teacher/{tb.id}", headers=school["adm"])
    # A keeps s2; delete A handing s2 to B as well
    _, tc = _make_teacher("tc@test.io")
    r = client.delete(f"{API}/admin/users/{_user_id('ta@test.io')}", headers=school["adm"],
                      params={"transfer_to": tc.id})
    assert r.status_code == 204
    with SessionLocal() as db:
        assert db.query(Subscription).filter_by(student_id=school["s1"].id).one().teacher_id == tb.id
        assert db.query(Subscription).filter_by(student_id=school["s2"].id).one().teacher_id == tc.id


def test_teacher_without_students_and_admin_rules(client, school):
    _make_teacher("empty@test.io")
    assert client.delete(f"{API}/admin/users/{_user_id('empty@test.io')}", headers=school["adm"]).status_code == 204
    # administrators are never deleted, including oneself
    assert client.delete(f"{API}/admin/users/{_user_id('school-admin@test.io')}",
                         headers=school["adm"]).status_code == 400
    assert client.delete(f"{API}/admin/users/999999", headers=school["adm"]).status_code == 404


def _make_teacher(email: str):
    from conftest import make_user

    from app.models.enums import UserRole
    return make_user(UserRole.TEACHER, email, name="Teacher New")
