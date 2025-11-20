# tests/test_dice_score.py
import io
import numpy as np
from fastapi.testclient import TestClient
import pytest

from app import main as app_main 
from app.main import app, REF_DATA  # REF_DATA is the in-memory reference dict


client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_results_file(tmp_path, monkeypatch):
    """
    For every test, redirect app.RESULTS_FILE to a temp location,
    so tests don't touch the real results.json.
    """
    tmp_results = tmp_path / "results_test.json"
    monkeypatch.setattr(app_main, "RESULTS_FILE", tmp_results)
    yield
    # optional: cleanup temp file (tmp_path will be wiped anyway)
    if tmp_results.exists():
        tmp_results.unlink()


def _make_npz_bytes(arrays_dict: dict[str, np.ndarray]) -> io.BytesIO:
    """
    Helper: pack dict of {key: array} into an in-memory .npz file.
    Returns a BytesIO object positioned at start.
    """
    buf = io.BytesIO()
    np.savez(buf, **arrays_dict)
    buf.seek(0)
    return buf


def test_perfect_submission_gets_high_score():
    """
    Use the reference segmentations as the prediction.
    Dice should be ~1.0 (exact 1.0 in ideal case).
    """
    npz_buf = _make_npz_bytes(REF_DATA)

    files = {
        "file": ("perfect_submission.npz", npz_buf, "application/octet-stream"),
    }
    data = {
        "name": "perfect_team",
    }

    response = client.post("/dice-score", files=files, data=data)
    assert response.status_code == 200, response.text

    payload = response.json()
    score = payload["score"]
    print("Perfect score:", score)

    assert score > 0.99  # small tolerance


def test_messy_submission_gets_lower_score():
    """
    Create intentionally bad predictions by shifting each array,
    then assert that the score is lower than the perfect one.
    """
    # First, compute the perfect score once
    perfect_buf = _make_npz_bytes(REF_DATA)
    resp_perfect = client.post(
        "/dice-score",
        files={"file": ("perfect.npz", perfect_buf, "application/octet-stream")},
        data={"name": "perfect_team"},
    )
    assert resp_perfect.status_code == 200
    perfect_score = resp_perfect.json()["score"]

    # Now create messy predictions by rolling each array
    bad_arrays = {
        key: np.roll(arr, shift=10, axis=0)  # shift along rows destroys alignment
        for key, arr in REF_DATA.items()
    }
    bad_buf = _make_npz_bytes(bad_arrays)

    resp_bad = client.post(
        "/dice-score",
        files={"file": ("bad_submission.npz", bad_buf, "application/octet-stream")},
        data={"name": "chaos_team"},
    )
    assert resp_bad.status_code == 200
    bad_score = resp_bad.json()["score"]
    print("Bad score:", bad_score, "Perfect score:", perfect_score)

    assert bad_score < perfect_score


def test_missing_subject_in_submission_returns_400():
    """
    Build a submission npz that is missing one subject key compared to REF_DATA.
    The endpoint should reject it with HTTP 400 and a clear error message.
    """
    # Copy REF_DATA but drop one subject
    keys = list(REF_DATA.keys())
    assert len(keys) > 1, "Need at least 2 subjects to test missing case"

    dropped_key = keys[0]
    partial_arrays = {k: REF_DATA[k] for k in keys[1:]}  # omit the first key

    npz_buf = _make_npz_bytes(partial_arrays)

    resp = client.post(
        "/dice-score",
        files={"file": ("incomplete_submission.npz", npz_buf, "application/octet-stream")},
        data={"name": "incomplete_team"},
    )

    assert resp.status_code == 400
    body = resp.json()
    print("Error response:", body)

    # Optional: check that the message mentions missing predictions
    assert "missing predictions for" in body.get("detail", "")
    assert dropped_key in body.get("detail", "")
