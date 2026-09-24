from web_app.bridge.auth import RecognitionGate


def face(idx="1", percent=91.0):
    return {"idx": idx, "rect": [0, 0, 10, 10], "score": None, "percent": percent}


def make_gate():
    return RecognitionGate(threshold=80, required_streak=3, window_s=10)


def test_three_consecutive_matches_recognize():
    gate = make_gate()
    assert gate.update(face(), 1, 0.0)["streak"] == 1
    assert gate.update(face(), 2, 0.5)["state"] == "searching"
    state = gate.update(face(), 3, 1.0)
    assert state["state"] == "recognized"
    assert state["idx"] == "1" and state["percent"] == 91.0


def test_non_match_resets_streak():
    gate = make_gate()
    gate.update(face(), 1, 0.0)
    gate.update(face(), 2, 0.5)
    assert gate.update(None, 3, 1.0)["streak"] == 0
    gate.update(face(), 4, 1.5)
    assert gate.update(face(), 5, 2.0)["state"] == "searching"


def test_repeated_frame_count_is_ignored():
    gate = make_gate()
    for _ in range(5):
        state = gate.update(face(), 7, 0.0)
    assert state["streak"] == 1
    assert state["state"] == "searching"


def test_wrong_idx_and_low_or_missing_percent_do_not_match():
    gate = make_gate()
    assert gate.update(face(idx="2"), 1, 0.0)["streak"] == 0
    assert gate.update(face(percent=79.9), 2, 0.1)["streak"] == 0
    assert gate.update(face(percent=None), 3, 0.2)["streak"] == 0
    assert gate.update(face(percent=80.0), 4, 0.3)["streak"] == 1


def test_streak_must_complete_within_window():
    gate = make_gate()
    gate.update(face(), 1, 0.0)
    gate.update(face(), 2, 9.0)
    state = gate.update(face(), 3, 10.5)  # 10.5 s after the first match: restart
    assert state["streak"] == 1
    assert state["state"] == "searching"


def test_reset_clears_recognition():
    gate = make_gate()
    for i in range(3):
        gate.update(face(), i + 1, float(i))
    assert gate.recognized
    gate.reset()
    assert gate.state()["state"] == "searching"
    assert gate.state()["streak"] == 0
