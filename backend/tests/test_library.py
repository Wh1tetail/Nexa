"""Stage 16: Methodist role, shared test library with sections and tags."""
import pytest
from conftest import PASSWORD, login, make_user
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import Attachment
from app.models.enums import UserRole

API = "/api/v1"
PNG = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000")
Q = [{"type": "single_choice", "text": "She ___ to school.", "points": 1, "correct_answer": ["a"],
      "options": [{"id": "a", "text": "goes"}, {"id": "b", "text": "go"}]}]
GAPS = {"type": "fill_gaps", "text": "Complete", "config": {"template": "I {am} here."}}


@pytest.fixture
def lib(client, school):
    make_user(UserRole.METHODIST, "method@test.io", name="Mila Methodist")
    hm = login(client, "method@test.io")
    # the migration seeds these; tests start from an empty database, so create them
    sections = {}
    for parent, children in {"Grammar": ["Present Simple"], "Vocabulary": ["Travel"]}.items():
        pid = client.post(f"{API}/library/sections", headers=hm, json={"name": parent}).json()["id"]
        sections[parent] = pid
        for c in children:
            sections[c] = client.post(f"{API}/library/sections", headers=hm, json={"name": c, "parent_id": pid}).json()["id"]
    return {**school, "hm": hm, "sec": sections}


def _create(client, lib, **fields):
    body = {"title": "Present Simple basics", "questions": Q, "level": "A2",
            "section_ids": [lib["sec"]["Present Simple"]], "tags": ["Routine", " daily  life "], **fields}
    r = client.post(f"{API}/library/tests", headers=lib["hm"], json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_drafts_are_hidden_until_published(client, lib):
    t = _create(client, lib)
    assert t["published"] is False and t["author_name"] == "Mila Methodist"
    assert t["tags"] == ["daily life", "routine"] and t["sections"][0]["name"] == "Present Simple"
    assert client.get(f"{API}/library/tests", headers=lib["ha"]).json() == []
    assert client.get(f"{API}/library/tests/{t['id']}", headers=lib["ha"]).status_code == 404

    body = {"title": t["title"], "questions": Q, "level": "A2", "section_ids": [lib["sec"]["Present Simple"]],
            "tags": ["routine"], "published": True}
    assert client.put(f"{API}/library/tests/{t['id']}", headers=lib["hm"], json=body).status_code == 200
    items = client.get(f"{API}/library/tests", headers=lib["ha"]).json()
    assert [i["id"] for i in items] == [t["id"]] and items[0]["questions_count"] == 1
    preview = client.get(f"{API}/library/tests/{t['id']}", headers=lib["ha"]).json()
    assert preview["questions"][0]["correct_answer"] == ["a"]  # teachers see the answers in the preview
    # the library is not a teacher's own test list, and teachers can't open it as theirs
    assert all(x["id"] != t["id"] for x in client.get(f"{API}/tests", headers=lib["ha"]).json())
    assert client.get(f"{API}/tests/{t['id']}", headers=lib["ha"]).status_code == 404


def test_rights(client, lib):
    t = _create(client, lib, published=True)
    body = {"title": "X", "questions": Q}
    for h in ("ha", "h1"):
        assert client.post(f"{API}/library/tests", headers=lib[h], json=body).status_code == 403
        assert client.put(f"{API}/library/tests/{t['id']}", headers=lib[h], json=body).status_code == 403
        assert client.delete(f"{API}/library/tests/{t['id']}", headers=lib[h]).status_code == 403
        assert client.post(f"{API}/library/sections", headers=lib[h], json={"name": "X"}).status_code == 403
    assert client.get(f"{API}/library/tests", headers=lib["h1"]).status_code == 403  # students
    # the methodist is not a teacher
    assert client.get(f"{API}/tests", headers=lib["hm"]).status_code == 403
    assert client.get(f"{API}/students", headers=lib["hm"]).status_code == 403
    # admins edit the library too
    assert client.put(f"{API}/library/tests/{t['id']}", headers=lib["adm"], json={**body, "published": True}).status_code == 200


def test_filters_and_counts(client, lib):
    sec = lib["sec"]
    a = _create(client, lib, published=True)
    b = _create(client, lib, title="Travel words", level="B1", section_ids=[sec["Travel"]], tags=["trip"],
                questions=[GAPS], published=True)
    _create(client, lib, title="Draft", published=False)

    def ids(**params):
        return [i["id"] for i in client.get(f"{API}/library/tests", headers=lib["ha"], params=params).json()]

    assert ids(level="B1") == [b["id"]]
    assert ids(section_id=sec["Grammar"]) == [a["id"]]  # a parent section includes its subsections
    assert ids(tag="TRIP") == [b["id"]]
    assert ids(question_type="fill_gaps") == [b["id"]]
    assert ids(search="travel") == [b["id"]]
    assert sorted(ids(author_id=a["author_id"])) == sorted([a["id"], b["id"]])
    # editors see drafts too and can filter them
    drafts = client.get(f"{API}/library/tests", headers=lib["hm"], params={"published": False}).json()
    assert [d["title"] for d in drafts] == ["Draft"]

    tree = {s["name"]: s for s in client.get(f"{API}/library/sections", headers=lib["ha"]).json()}
    assert tree["Grammar"]["tests_count"] == 1 and tree["Grammar"]["direct_count"] == 0
    assert tree["Present Simple"]["direct_count"] == 1  # the draft is not counted for teachers
    edit_tree = {s["name"]: s for s in client.get(f"{API}/library/sections", headers=lib["hm"]).json()}
    assert edit_tree["Present Simple"]["direct_count"] == 2
    tags = {t["name"]: t["tests_count"] for t in client.get(f"{API}/library/tags", headers=lib["ha"]).json()}
    assert tags == {"daily life": 1, "routine": 1, "trip": 1}


def test_sections_tree_and_moving_tests(client, lib):
    sec = lib["sec"]
    r = client.post(f"{API}/library/sections", headers=lib["hm"], json={"name": "Phrasal Verbs", "parent_id": sec["Vocabulary"]})
    assert r.status_code == 201 and r.json()["parent_id"] == sec["Vocabulary"]
    pv = r.json()["id"]
    # no loops: a section can't go inside its own subsection
    assert client.patch(f"{API}/library/sections/{sec['Vocabulary']}", headers=lib["hm"],
                        json={"parent_id": pv}).status_code == 400
    assert client.patch(f"{API}/library/sections/{pv}", headers=lib["hm"], json={"name": "Phrasal verbs"}).json()["name"] == "Phrasal verbs"

    t = _create(client, lib, published=True)  # in Present Simple
    # add to a second section, then move out of the first
    assert client.post(f"{API}/library/tests/move", headers=lib["hm"],
                       json={"test_ids": [t["id"]], "section_id": pv}).status_code == 204
    detail = client.get(f"{API}/library/tests/{t['id']}", headers=lib["hm"]).json()
    assert sorted(s["name"] for s in detail["sections"]) == ["Phrasal verbs", "Present Simple"]
    client.post(f"{API}/library/tests/move", headers=lib["hm"],
                json={"test_ids": [t["id"]], "section_id": pv, "from_section_id": sec["Present Simple"]})
    detail = client.get(f"{API}/library/tests/{t['id']}", headers=lib["hm"]).json()
    assert [s["name"] for s in detail["sections"]] == ["Phrasal verbs"]

    # deleting a section removes its subsections, never the tests
    assert client.delete(f"{API}/library/sections/{sec['Vocabulary']}", headers=lib["hm"]).status_code == 204
    names = {s["name"] for s in client.get(f"{API}/library/sections", headers=lib["hm"]).json()}
    assert "Vocabulary" not in names and "Phrasal verbs" not in names and "Grammar" in names
    assert client.get(f"{API}/library/tests/{t['id']}", headers=lib["hm"]).json()["sections"] == []


def test_teacher_copy_is_independent(client, lib):
    t = _create(client, lib, published=True)
    up = client.post(f"{API}/library/tests/{t['id']}/files", headers=lib["hm"],
                     files=[("files", ("pic.png", PNG, "image/png"))])
    assert up.status_code == 201, up.text
    file_id = up.json()[0]["id"]
    q = {**Q[0], "attachment_ids": [file_id]}
    client.put(f"{API}/library/tests/{t['id']}", headers=lib["hm"], json={
        "title": t["title"], "questions": [q], "published": True})
    # teachers can see published library files
    assert client.get(f"{API}/files/{file_id}", headers=lib["ha"]).status_code == 200

    r = client.post(f"{API}/library/tests/{t['id']}/copy", headers=lib["ha"])
    assert r.status_code == 201, r.text
    mine = r.json()
    assert mine["id"] != t["id"] and mine["student_ids"] == [] and len(mine["files"]) == 1
    new_file = mine["files"][0]["id"]
    assert new_file != file_id and mine["questions"][0]["attachment_ids"] == [new_file]
    with SessionLocal() as db:
        keys = {a.id: a.storage_key for a in db.scalars(select(Attachment).where(Attachment.id.in_([file_id, new_file])))}
    assert keys[file_id] != keys[new_file]  # the file itself is copied
    # the teacher edits and assigns the copy; the original does not change
    body = {"title": "My version", "questions": Q, "student_ids": [lib["s1"].id]}
    assert client.put(f"{API}/tests/{mine['id']}", headers=lib["ha"], json=body).status_code == 200
    assert client.get(f"{API}/library/tests/{t['id']}", headers=lib["ha"]).json()["title"] == t["title"]
    assert client.get(f"{API}/library/tests", headers=lib["ha"]).json()[0]["copies"] == 1
    # deleting the copy keeps the library file
    assert client.delete(f"{API}/tests/{mine['id']}", headers=lib["ha"]).status_code == 204
    assert client.get(f"{API}/files/{file_id}", headers=lib["ha"]).status_code == 200
    # a draft can't be copied by a teacher; the methodist can duplicate anything
    draft = _create(client, lib, title="Draft")
    assert client.post(f"{API}/library/tests/{draft['id']}/copy", headers=lib["ha"]).status_code == 404
    dup = client.post(f"{API}/library/tests/{t['id']}/duplicate", headers=lib["hm"]).json()
    assert dup["title"].endswith("(copy)") and dup["published"] is False and len(dup["files"]) == 1


def test_admin_creates_a_methodist(client, school):
    r = client.post(f"{API}/admin/methodists", headers=school["adm"], json={
        "email": "New.Methodist@test.io", "full_name": "Nina Methodist", "password": PASSWORD, "send_invite": False})
    assert r.status_code == 201, r.text
    assert r.json()["role"] == "methodist"
    h = login(client, "new.methodist@test.io")
    assert client.get(f"{API}/auth/me", headers=h).json()["role"] == "methodist"
    assert client.post(f"{API}/admin/methodists", headers=school["ha"], json={
        "email": "x@test.io", "full_name": "X Y", "password": PASSWORD}).status_code == 403
    users = client.get(f"{API}/admin/users", headers=school["adm"], params={"role": "methodist"}).json()
    assert [u["email"] for u in users] == ["new.methodist@test.io"]
