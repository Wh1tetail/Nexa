"""Editing a weekly lesson series: scope=one|following, time shift, participants,
cancellation, protection of completed lessons, extension, notifications."""
from datetime import UTC, datetime, timedelta

API = "/api/v1"


def _series(client, school, weeks=3, start=None):
    start = start or (datetime.now(UTC) + timedelta(days=1)).replace(hour=16, minute=0, second=0, microsecond=0)
    r = client.post(f"{API}/lessons", headers=school["aa"], json={
        "title": "Club", "topic": "Intro", "starts_at": start.isoformat(),
        "student_ids": [school["s1"].id], "repeat_weeks": weeks})
    assert r.status_code == 201, r.text
    sid = r.json()["series_id"]
    lessons = [x for x in client.get(f"{API}/lessons", headers=school["ha"]).json() if x["series_id"] == sid]
    return sorted(lessons, key=lambda x: x["starts_at"])


def _get(client, school, lid):
    return client.get(f"{API}/lessons/{lid}", headers=school["ha"]).json()


def test_series_position(client, school):
    lessons = _series(client, school, weeks=3)
    assert [(x["series_position"], x["series_total"]) for x in lessons] == [(1, 4), (2, 4), (3, 4), (4, 4)]


def test_edit_only_this(client, school):
    lessons = _series(client, school)
    r = client.patch(f"{API}/lessons/{lessons[1]['id']}?scope=one", headers=school["ha"], json={"topic": "Changed"})
    assert r.status_code == 200
    topics = [_get(client, school, x["id"])["topic"] for x in lessons]
    assert topics == ["Intro", "Changed", "Intro", "Intro"]


def test_edit_following_shifts_time_and_updates_fields(client, school):
    lessons = _series(client, school)
    second = lessons[1]
    new_start = datetime.fromisoformat(second["starts_at"]) + timedelta(hours=1, minutes=30)
    r = client.patch(f"{API}/lessons/{second['id']}?scope=following", headers=school["aa"], json={
        "starts_at": new_start.isoformat(), "topic": "Advanced", "duration_minutes": 90,
        "student_ids": [school["s1"].id, school["s2"].id]})
    assert r.status_code == 200, r.text
    after = [_get(client, school, x["id"]) for x in lessons]
    # first lesson untouched
    assert after[0]["topic"] == "Intro" and after[0]["starts_at"] == lessons[0]["starts_at"]
    for before, now in zip(lessons[1:], after[1:], strict=True):
        delta = datetime.fromisoformat(now["starts_at"]) - datetime.fromisoformat(before["starts_at"])
        assert delta == timedelta(hours=1, minutes=30)  # weekday kept, time shifted
        assert now["topic"] == "Advanced" and now["duration_minutes"] == 90
        assert {a["student_id"] for a in now["attendance"]} == {school["s1"].id, school["s2"].id}
    # one aggregated notification per student, not one per lesson
    notes = client.get(f"{API}/notifications", headers=school["h1"]).json()
    changed = [n for n in notes if n["type"] == "lesson_changed"]
    assert len(changed) == 1 and "занятий — 3" in changed[0]["body"]
    assert any(n["type"] == "lesson_changed" for n in client.get(f"{API}/notifications", headers=school["h2"]).json())


def test_completed_lessons_are_protected(client, school):
    start = (datetime.now(UTC) - timedelta(days=8)).replace(microsecond=0)
    lessons = _series(client, school, weeks=3, start=start)  # first two are in the past
    client.put(f"{API}/lessons/{lessons[1]['id']}/attendance", headers=school["ha"],
               json={"marks": [{"student_id": school["s1"].id, "status": "present"}]})
    assert _get(client, school, lessons[1]["id"])["status"] == "completed"
    r = client.patch(f"{API}/lessons/{lessons[0]['id']}?scope=following", headers=school["aa"], json={"title": "Renamed"})
    assert r.status_code == 200
    titles = [_get(client, school, x["id"])["title"] for x in lessons]
    assert titles == ["Renamed", "Club", "Renamed", "Renamed"]  # completed lesson kept as is


def test_cancel_following(client, school):
    lessons = _series(client, school)
    client.patch(f"{API}/lessons/{lessons[2]['id']}?scope=following", headers=school["aa"], json={"status": "cancelled"})
    statuses = [_get(client, school, x["id"])["status"] for x in lessons]
    assert statuses == ["scheduled", "scheduled", "cancelled", "cancelled"]
    # restoring one cancelled lesson does not touch others (cancelled ones are not "scheduled" followers)
    client.patch(f"{API}/lessons/{lessons[2]['id']}?scope=following", headers=school["aa"], json={"status": "scheduled"})
    statuses = [_get(client, school, x["id"])["status"] for x in lessons]
    assert statuses == ["scheduled", "scheduled", "scheduled", "cancelled"]


def test_extend_series_and_single_lesson(client, school):
    lessons = _series(client, school, weeks=1)
    r = client.post(f"{API}/lessons/{lessons[0]['id']}/series/extend", headers=school["aa"], json={"weeks": 2})
    assert r.status_code == 200 and r.json()["series_total"] == 4
    all_ = sorted((x for x in client.get(f"{API}/lessons", headers=school["ha"]).json()
                   if x["series_id"] == lessons[0]["series_id"]), key=lambda x: x["starts_at"])
    gaps = {(datetime.fromisoformat(b["starts_at"]) - datetime.fromisoformat(a["starts_at"])).days for a, b in zip(all_, all_[1:])}
    assert gaps == {7}
    # a single lesson becomes a series
    single = client.post(f"{API}/lessons", headers=school["aa"], json={
        "title": "One", "starts_at": datetime.now(UTC).isoformat(), "student_ids": [school["s2"].id]}).json()
    assert single["series_id"] is None
    r = client.post(f"{API}/lessons/{single['id']}/series/extend", headers=school["aa"], json={"weeks": 3})
    assert r.json()["series_id"] and r.json()["series_total"] == 4
    # validation & ownership
    assert client.post(f"{API}/lessons/{single['id']}/series/extend", headers=school["aa"], json={"weeks": 0}).status_code == 422
    assert client.post(f"{API}/lessons/{single['id']}/series/extend", headers=school["ab"], json={"weeks": 1}).status_code == 404
    assert client.patch(f"{API}/lessons/{single['id']}?scope=following", headers=school["hb"], json={"title": "x"}).status_code == 404
