"""Stage 15: audio and reading blocks, Fill in the Gaps, Matching."""
API = "/api/v1"
PNG = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000")
MP3 = b"ID3\x03\x00\x00\x00\x00\x00\x0f" + b"\x00" * 64
OGG = b"OggS\x00\x02" + b"\x00" * 64


def _new_test(client, school, questions, **fields):
    r = client.post(f"{API}/tests", headers=school["ha"], json={
        "title": "Listening & Reading", "questions": questions, "student_ids": [school["s1"].id], **fields})
    assert r.status_code == 201, r.text
    return r.json()


def _upload(client, school, test_id, files):
    r = client.post(f"{API}/tests/{test_id}/files", headers=school["ha"], files=[("files", f) for f in files])
    assert r.status_code in (200, 201), r.text
    return {f["original_name"]: f["id"] for f in r.json()}


SC = {"type": "single_choice", "text": "Warm-up", "points": 1, "correct_answer": ["a"],
      "options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}]}


def _build(client, school, **fields):
    """Test: audio block, gaps, matching, reading block, 3 questions on the text."""
    t = _new_test(client, school, [SC])
    files = _upload(client, school, t["id"], [("dialogue.mp3", MP3, "audio/mpeg"), ("park.png", PNG, "image/png")])
    questions = [
        {"type": "audio", "text": "Dialogue 1", "points": 0,
         "config": {"attachment_id": files["dialogue.mp3"], "max_plays": 2, "body": "Listen and answer."}},
        {"type": "fill_gaps", "text": "Complete the text", "config": {
            "template": "Tom usually {goes::go} to school. He {likes|loves} English and { studies } every day.",
            "gap_points": [1, 2, 1], "mode": "input"}},
        {"type": "matching", "text": "Match the words", "points": 4, "config": {
            "pairs": [{"left": "apple", "right": "яблоко"}, {"left": "dog", "right": "собака"},
                      {"left": "house", "right": "дом"}, {"left": "book", "right": "книга"}],
            "distractors": ["кот"]}},
        {"type": "reading", "text": "A day in the park", "points": 0,
         "config": {"body": "## Park\n\nAnna goes to the **park** every Sunday.", "image_id": files["park.png"]}},
        {"type": "true_false", "text": "Anna goes to the park on Sunday.", "correct_answer": ["true"]},
        {"type": "multiple_choice", "text": "What is true?", "correct_answer": ["a", "b"],
         "options": [{"id": "a", "text": "She goes on Sunday"}, {"id": "b", "text": "It's a park"},
                     {"id": "c", "text": "She hates it"}]},
        {"type": "short_answer", "text": "Who goes to the park?", "correct_answer": ["Anna"]},
    ]
    body = {"title": "Listening & Reading", "questions": questions, "student_ids": [school["s1"].id], **fields}
    r = client.put(f"{API}/tests/{t['id']}", headers=school["ha"], json=body)
    assert r.status_code == 200, r.text
    return r.json(), files


def _q(detail, qtype):
    return next(q for q in detail["questions"] if q["type"] == qtype)


def test_blocks_and_new_types_are_stored_and_hidden_from_students(client, school):
    t, files = _build(client, school)
    gaps, match = _q(t, "fill_gaps"), _q(t, "matching")
    assert gaps["points"] == 4 and match["points"] == 4 and _q(t, "audio")["points"] == 0
    assert gaps["config"]["answers"] == [["goes"], ["likes", "loves"], ["studies"]]  # the teacher sees everything
    item = client.get(f"{API}/me/tests", headers=school["h1"]).json()[0]
    assert item["questions_count"] == 5  # blocks are not questions

    a = client.post(f"{API}/me/tests/{t['id']}/start", headers=school["h1"]).json()
    g, m = _q(a, "fill_gaps"), _q(a, "matching")
    assert "answers" not in g["config"] and "template" not in g["config"]
    assert g["config"]["segments"][0] == "Tom usually " and g["config"]["gaps"][0]["hint"] == "go"
    assert "answers" not in m["config"] and sorted(m["config"]["rights"]) == sorted(["яблоко", "собака", "дом", "книга", "кот"])
    assert m["config"]["lefts"] == ["apple", "dog", "house", "book"]
    reading = _q(a, "reading")
    assert reading["config"]["image_id"] == files["park.png"] and "**park**" in reading["config"]["body"]
    # reloading keeps the same shuffled order
    again = client.post(f"{API}/me/tests/{t['id']}/start", headers=school["h1"]).json()
    assert _q(again, "matching")["config"]["rights"] == m["config"]["rights"]
    # the audio and the picture are available during the test
    assert client.get(f"{API}/files/{files['dialogue.mp3']}", headers=school["h1"]).status_code == 200


def test_scoring_gaps_matching_and_reading_questions(client, school):
    t, _ = _build(client, school)
    a = client.post(f"{API}/me/tests/{t['id']}/start", headers=school["h1"]).json()
    ids = {q["type"]: q["id"] for q in a["questions"]}
    answers = [
        # case and extra spaces are ignored; the alternative "loves" counts; the last gap is wrong
        {"question_id": ids["fill_gaps"], "answer": ["  GOES ", "loves", "study"]},
        {"question_id": ids["matching"], "answer": ["яблоко", "собака", "кот", "книга"]},  # 3 of 4
        {"question_id": ids["true_false"], "answer": ["true"]},
        {"question_id": ids["multiple_choice"], "answer": ["a", "b"]},
        {"question_id": ids["short_answer"], "answer": ["anna"]},
        {"question_id": ids["audio"], "answer": ["ignored"]},
    ]
    r = client.post(f"{API}/me/tests/attempts/{a['id']}/submit", headers=school["h1"], json={"answers": answers})
    assert r.status_code == 200, r.text
    res = r.json()
    by_q = {x["question_id"]: x for x in res["answers"]}
    assert ids["audio"] not in by_q and ids["reading"] not in by_q  # blocks take no answers
    assert by_q[ids["fill_gaps"]]["points_awarded"] == 3 and by_q[ids["fill_gaps"]]["is_correct"] is False
    assert by_q[ids["matching"]]["points_awarded"] == 3 and by_q[ids["matching"]]["is_correct"] is False
    assert res["status"] == "graded"
    assert res["score"] == 3 + 3 + 1 + 1 + 1 and res["max_score"] == 4 + 4 + 1 + 1 + 1
    # after grading (answers allowed) the student sees the correct answers
    assert _q(res, "fill_gaps")["config"]["answers"][2] == ["studies"]
    assert _q(res, "matching")["config"]["answers"] == ["яблоко", "собака", "дом", "книга"]


def test_case_sensitive_gaps_and_word_bank_modes(client, school):
    q = {"type": "fill_gaps", "text": "Names", "config": {
        "template": "{London} is big. {paris} is old.", "mode": "dropdown", "case_sensitive": True,
        "distractors": ["Rome", "Berlin"]}}
    t = _new_test(client, school, [q])
    a = client.post(f"{API}/me/tests/{t['id']}/start", headers=school["h1"]).json()
    cfg = a["questions"][0]["config"]
    assert cfg["mode"] == "dropdown" and sorted(cfg["bank"]) == ["Berlin", "London", "Rome", "paris"]
    r = client.post(f"{API}/me/tests/attempts/{a['id']}/submit", headers=school["h1"], json={"answers": [
        {"question_id": a["questions"][0]["id"], "answer": ["london", "paris"]}]}).json()
    assert r["score"] == 1  # "london" != "London" when the case matters


def test_listening_limit(client, school):
    t, _ = _build(client, school)
    a = client.post(f"{API}/me/tests/{t['id']}/start", headers=school["h1"]).json()
    audio = _q(a, "audio")
    url = f"{API}/me/tests/attempts/{a['id']}/plays/{audio['id']}"
    assert client.post(url, headers=school["h1"]).json() == {"plays": 1, "max_plays": 2, "allowed": True}
    assert client.post(url, headers=school["h1"]).json()["plays"] == 2
    r = client.post(url, headers=school["h1"])
    assert r.status_code == 400 and r.json()["detail"] == "Лимит прослушиваний исчерпан"
    # the count survives a reload
    assert client.post(f"{API}/me/tests/{t['id']}/start", headers=school["h1"]).json()["plays"] == {str(audio["id"]): 2}
    # only audio blocks, only one's own attempt
    other = _q(a, "true_false")["id"]
    assert client.post(f"{API}/me/tests/attempts/{a['id']}/plays/{other}", headers=school["h1"]).status_code == 404
    assert client.post(url, headers=school["h2"]).status_code == 404
    # after the test the recording can be replayed
    client.post(f"{API}/me/tests/attempts/{a['id']}/submit", headers=school["h1"], json={"answers": []})
    assert client.post(url, headers=school["h1"]).json()["allowed"] is True


def test_shuffling_keeps_blocks_in_place(client, school):
    t, _ = _build(client, school, shuffle_questions=True)
    for student in ("h1",):
        a = client.post(f"{API}/me/tests/{t['id']}/start", headers=school[student]).json()
        types = [q["type"] for q in a["questions"]]
        audio, reading = types.index("audio"), types.index("reading")
        # the 3 reading questions stay after the reading block, the rest before it
        assert sorted(types[reading + 1:]) == ["multiple_choice", "short_answer", "true_false"]
        assert audio < reading and set(types[audio + 1:reading]) == {"fill_gaps", "matching"}


def test_validation(client, school):
    t = _new_test(client, school, [SC])
    files = _upload(client, school, t["id"], [("park.png", PNG, "image/png"), ("song.ogg", OGG, "audio/ogg")])
    base = {"title": "X", "student_ids": []}

    def put(question):
        return client.put(f"{API}/tests/{t['id']}", headers=school["ha"], json={**base, "questions": [question]})

    assert put({"type": "fill_gaps", "text": "No gaps", "config": {"template": "Nothing here"}}).status_code == 422
    assert put({"type": "fill_gaps", "text": "Empty", "config": {"template": "A {  } gap"}}).status_code == 422
    assert put({"type": "matching", "text": "One pair", "config": {"pairs": [{"left": "a", "right": "b"}]}}).status_code == 422
    assert put({"type": "reading", "text": "No text", "config": {"body": "  "}}).status_code == 422
    assert put({"type": "audio", "text": "A", "config": {"attachment_id": files["park.png"]}}).status_code == 400  # not audio
    assert put({"type": "audio", "text": "A", "config": {"attachment_id": 999999}}).status_code == 400  # not this test's
    assert put({"type": "audio", "text": "A", "config": {"attachment_id": files["song.ogg"], "max_plays": 0}}).status_code == 422
    r = put({"type": "audio", "text": "OGG works", "config": {"attachment_id": files["song.ogg"]}})
    assert r.status_code == 200 and r.json()["questions"][0]["config"]["max_plays"] is None
