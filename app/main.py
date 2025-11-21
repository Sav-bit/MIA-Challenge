# app/main.py
import json
import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Dict

from fastapi.templating import Jinja2Templates
import numpy as np
import SimpleITK as sitk
from fastapi import FastAPI, File, Form, Request, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

logger = logging.getLogger(__name__)
app = FastAPI()

REFERENCE_FILE = Path(os.getenv("REFERENCE_FILE", "data/test_data_reference.npz"))
RESULTS_FILE = Path(os.getenv("RESULTS_FILE", "data/results.json"))
templates = Jinja2Templates(directory="app/templates")
NAME_RE = re.compile(r"^[A-Za-z0-9 _\-\.\(\)]{1,40}$")
MAX_BYTES = 1 * 1024 * 1024 # 1 MB

# Load reference once at startup
if not REFERENCE_FILE.exists():
    raise RuntimeError(f"Reference NPZ not found at {REFERENCE_FILE}")

_ref_npz = np.load(REFERENCE_FILE)
# Convert to a plain dict so we don't depend on an open file handle
REF_DATA: dict[str, np.ndarray] = {k: _ref_npz[k] for k in _ref_npz.files}
del _ref_npz

print(f"Loaded reference with {len(REF_DATA)} subjects: {sorted(REF_DATA.keys())}")


def dice_for_subject(pred_slice: np.ndarray, ref_slice: np.ndarray) -> float:
    """
    Macro Dice for a single subject (2D slice), multi-class, background = 0.
    Macro = mean of per-class Dice over all non-zero labels.
    """
    if pred_slice.shape != ref_slice.shape:
        raise ValueError(
            f"Shape mismatch: pred {pred_slice.shape} vs ref {ref_slice.shape}"
        )

    pred_flat = pred_slice.ravel()
    ref_flat = ref_slice.ravel()

    labels = np.union1d(pred_flat, ref_flat)
    labels = labels[labels != 0]  # ignore background label 0

    if labels.size == 0:
        # No foreground at all -> define Dice = 1 for this subject
        return 1.0

    per_class: dict[int, float] = {}

    for lab in labels:
        pred_mask = pred_flat == lab
        ref_mask = ref_flat == lab

        intersection = np.logical_and(pred_mask, ref_mask).sum()
        size_sum = pred_mask.sum() + ref_mask.sum()

        if size_sum == 0:
            dice_lab = 1.0  # both empty for this class
        else:
            dice_lab = 2.0 * intersection / size_sum

        per_class[int(lab)] = float(dice_lab)

    # macro over classes
    return float(np.mean(list(per_class.values())))


def calculate_mean_dice_from_npz(
    pred_npz_path: Path, ref_data: dict[str, np.ndarray]
) -> tuple[float, dict[str, float]]:
    """
    Compute mean macro Dice over all subjects.

    - ref_data: dict {subject_id: 2D GT array}
    - pred_npz_path: .npz file with matching keys -> predicted arrays
    """
    try:
        pred = np.load(pred_npz_path)
    except Exception as e:
        raise ValueError(f"Could not load prediction npz: {e}")

    ref_keys = set(ref_data.keys())
    pred_keys = set(pred.files)

    if ref_keys != pred_keys:
        missing = ref_keys - pred_keys
        extra = pred_keys - ref_keys
        msg_parts = []
        if missing:
            msg_parts.append(f"missing predictions for: {sorted(missing)}")
        if extra:
            msg_parts.append(f"unexpected subjects in submission: {sorted(extra)}")
        raise ValueError(
            "Key mismatch between reference and prediction npz: " + "; ".join(msg_parts)
        )

    per_subject_scores: dict[str, float] = {}
    all_scores: list[float] = []

    for key in sorted(ref_data.keys()):
        ref_slice = ref_data[key]
        pred_slice = pred[key]
        score = dice_for_subject(pred_slice, ref_slice)
        per_subject_scores[key] = score
        all_scores.append(score)

    mean_dice = float(np.mean(all_scores))
    print(f"Per-subject Dice: {per_subject_scores}")
    print(f"Mean Dice over subjects: {mean_dice}")

    return mean_dice, per_subject_scores


@app.post("/dice-score")
async def calculate_dice(file: UploadFile = File(...), name: str = Form(...)):

    name = name.strip()

    # Validate name
    if not NAME_RE.match(name):
        raise HTTPException(
            status_code=400,
            detail="Name must be 1-40 characters long and contain only letters, numbers, spaces, and - _ . ( )",
        )

    if not file.filename.endswith(".npz"):
        raise HTTPException(status_code=400, detail="File must be a .npz file")

    try:
        # Save uploaded npz temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".npz") as tmp_file:
            contents = await file.read()
            
            #If the file is too large, raise an error
            if len(contents) > MAX_BYTES:
                raise HTTPException(413, "File too large")
            
            tmp_file.write(contents)
            tmp_file_path = Path(tmp_file.name)

        try:
            # Use in-memory REF_DATA
            try:
                mean_dice, per_subject = calculate_mean_dice_from_npz(
                    tmp_file_path, REF_DATA
                )
            except ValueError as ve:
                raise HTTPException(status_code=400, detail=str(ve))

            result = {
                "score": mean_dice,
                "name": name,
                "per_subject": per_subject,
            }

            if RESULTS_FILE.exists():
                with open(RESULTS_FILE, "r") as f:
                    results = json.load(f)
            else:
                results = []

            results.append(result)

            with open(RESULTS_FILE, "w") as f:
                json.dump(results, f, indent=2)

            return JSONResponse(content=result, status_code=200)

        finally:
            if tmp_file_path.exists():
                tmp_file_path.unlink()

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error calculating dice score: {e}")
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred while processing the request",
        )


@app.get("/podium", response_class=HTMLResponse)
async def podium(request: Request):
    # If no results yet, show empty podium
    if not RESULTS_FILE.exists():
        return templates.TemplateResponse(
            "podium.html",
            {
                "request": request,
                "top3": [],
                "others": [],
            },
        )

    try:
        with open(RESULTS_FILE, "r") as f:
            results: list[Dict] = json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not read results: {e}")

    # Best score per name
    best_by_name: Dict[str, float] = {}
    for r in results:
        name = r.get("name")
        score = float(r.get("score", 0.0))
        if name is None:
            continue
        best_by_name[name] = max(best_by_name.get(name, 0.0), score)

    # Build leaderboard sorted by score desc
    leaderboard = sorted(
        [{"name": n, "score": s} for n, s in best_by_name.items()],
        key=lambda x: x["score"],
        reverse=True,
    )

    top3 = leaderboard[:3]
    others = leaderboard[3:]

    return templates.TemplateResponse(
        "podium.html",
        {
            "request": request,
            "top3": top3,
            "others": others,
        },
    )
