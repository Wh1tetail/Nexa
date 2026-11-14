"""User time zones: profile setting, DST-safe weekly series, notification texts
and CSV export in the right local time."""
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from app.core.timezones import add_weeks_local, fmt_local, shift_wall_clock, wall_clock_delta

API = "/api/v1"
BERLIN = ZoneInfo("Europe/Berlin")  # EU DST in 2027 starts on 28 March


def _set_tz(client, headers, tz):
    r = client.patch(f"{API}/auth/me", headers=headers, json={"timezone": tz})
    assert r.status_code == 200, r.text
    return r.json()


def _series(client, school, local_start: datetime, weeks: int):
    r = client.post(f"{API}/lessons", headers=school["ha"], json={
        "title": "Club", "starts_at": local_start.isoformat(), "student_ids": [school["s1"].id, school["s2"].id],
        "repeat_weeks": weeks})
    assert r.status_code == 201, r.text
    sid = r.json()["series_id"]
    lessons = [x for x in client.get(f"{API}/lessons", headers=school["ha"]).json() if x["series_id"] == sid]
    return sorted(lessons, key=lambda x: x["starts_at"])


def _local(iso: str, tz=BERLIN) -> datetime:
    return datetime.fromisoformat(iso).astimezone(tz)


def test_profile_timezone(client, school):
    me = client.get(f"{API}/auth/me", headers=school["ha"]).json()
    assert me["timezone"] is None  # not chosen yet -> server default is used
    assert _set_tz(client, school["ha"], "Asia/Yekaterinburg")["timezone"] == "Asia/Yekaterinburg"
    bad = client.patch(f"{API}/auth/me", headers=school["ha"], json={"timezone": "Mars/Olympus"})
    assert bad.status_code == 422


def test_helpers_are_dst_safe():
    start = datetime(2027, 3, 21, 18, 0, tzinfo=BERLIN)  # CET, UTC+1
    nxt = add_weeks_local(start, 1, BERLIN)  # CEST, UTC+2
    assert nxt.astimezone(BERLIN).hour == 18
    assert nxt - start == timedelta(days=7, hours=-1)  # only 167 real hours
    # 02:30 on 28 March 2027 does not exist in Berlin: resolves to a real instant
    gap = add_weeks_local(datetime(2027, 3, 21, 2, 30, tzinfo=BERLIN), 1, BERLIN)
    assert gap.astimezone(BERLIN).hour in (1, 3)
    d = wall_clock_delta(start, start + timedelta(hours=1, minutes=30), BERLIN)
    assert d == timedelta(hours=1, minutes=30)
    moved = shift_wall_clock(nxt, d, BERLIN).astimezone(BERLIN)
    assert (moved.hour, moved.minute) == (19, 30)
    assert fmt_local(start, BERLIN) == "21.03.2027 18:00 (Europe/Berlin)"


def test_series_keeps_local_time_across_dst(client, school):
    _set_tz(client, school["ha"], "Europe/Berlin")
    lessons = _series(client, school, datetime(2027, 3, 21, 18, 0, tzinfo=BERLIN), weeks=2)
    assert [(_local(x["starts_at"]).hour, _local(x["starts_at"]).minute) for x in lessons] == [(18, 0)] * 3
    # in UTC the clock jumps by an hour at the DST switch
    assert [datetime.fromisoformat(x["starts_at"]).astimezone(UTC).hour for x in lessons] == [17, 16, 16]

    # extending the series also keeps 18:00 local
    client.post(f"{API}/lessons/{lessons[0]['id']}/series/extend", headers=school["ha"], json={"weeks": 1})
    every = sorted((x for x in client.get(f"{API}/lessons", headers=school["ha"]).json()
                    if x["series_id"] == lessons[0]["series_id"]), key=lambda x: x["starts_at"])
    assert len(every) == 4 and _local(every[-1]["starts_at"]).hour == 18
    assert _local(every[-1]["starts_at"]).date().isoformat() == "2027-04-11"


def test_shift_following_uses_local_clock(client, school):
    _set_tz(client, school["ha"], "Europe/Berlin")
    lessons = _series(client, school, datetime(2027, 3, 21, 18, 0, tzinfo=BERLIN), weeks=2)
    # move the FIRST lesson (still winter time) to 19:30 for it and all following
    new_start = datetime(2027, 3, 21, 19, 30, tzinfo=BERLIN)
    r = client.patch(f"{API}/lessons/{lessons[0]['id']}?scope=following", headers=school["ha"],
                     json={"starts_at": new_start.isoformat()})
    assert r.status_code == 200
    after = [client.get(f"{API}/lessons/{x['id']}", headers=school["ha"]).json() for x in lessons]
    assert [(_local(x["starts_at"]).hour, _local(x["starts_at"]).minute) for x in after] == [(19, 30)] * 3


def test_notification_text_in_each_students_time_zone(client, school):
    _set_tz(client, school["h1"], "Asia/Yekaterinburg")  # UTC+5; student 2 keeps the default (Moscow, UTC+3)
    start = datetime(2027, 1, 10, 12, 0, tzinfo=UTC)
    lesson = client.post(f"{API}/lessons", headers=school["ha"], json={
        "title": "Grammar", "starts_at": start.isoformat(),
        "student_ids": [school["s1"].id, school["s2"].id]}).json()
    client.patch(f"{API}/lessons/{lesson['id']}", headers=school["ha"],
                 json={"starts_at": (start + timedelta(hours=1)).isoformat()})  # 13:00 UTC
    n1 = next(n for n in client.get(f"{API}/notifications", headers=school["h1"]).json() if n["type"] == "lesson_changed")
    n2 = next(n for n in client.get(f"{API}/notifications", headers=school["h2"]).json() if n["type"] == "lesson_changed")
    assert "10.01.2027 18:00 (Asia/Yekaterinburg)" in n1["body"]
    assert "10.01.2027 16:00 (Europe/Moscow)" in n2["body"]
    assert "UTC" not in n1["body"] + n2["body"]


def test_csv_export_uses_teacher_time_zone(client, school):
    _set_tz(client, school["ha"], "Asia/Vladivostok")  # UTC+10
    r = client.post(f"{API}/lessons", headers=school["ha"], json={
        "title": "Late", "starts_at": datetime(2027, 1, 10, 20, 0, tzinfo=UTC).isoformat(),
        "student_ids": [school["s1"].id]})
    client.put(f"{API}/lessons/{r.json()['id']}/attendance", headers=school["ha"],
               json={"marks": [{"student_id": school["s1"].id, "status": "present"}]})
    text = client.get(f"{API}/attendance/export", headers=school["ha"]).content.decode("utf-8-sig")
    header, row = text.splitlines()[0], text.splitlines()[1]
    assert "Дата (Asia/Vladivostok)" in header
    assert row.startswith("11.01.2027;06:00;")  # 20:00 UTC = 06:00 next day in Vladivostok
