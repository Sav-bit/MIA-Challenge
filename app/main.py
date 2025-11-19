# app/main.py
import json
import logging
import os
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

# You can set these via env vars or a config file
REFERENCE_FILE = Path(os.getenv("REFERENCE_FILE", "data/reference.nii.gz"))
RESULTS_FILE = Path(os.getenv("RESULTS_FILE", "data/results.json"))
templates = Jinja2Templates(directory="app/templates")


def calculate_dice_score(prediction: sitk.Image, reference: sitk.Image) -> float:
    overlap = sitk.LabelOverlapMeasuresImageFilter()
    overlap.Execute(reference, prediction)

    ref = sitk.GetArrayViewFromImage(reference)
    pred = sitk.GetArrayViewFromImage(prediction)

    labels = sorted(set(ref.ravel()) | set(pred.ravel()))
    labels = [lab for lab in labels if lab != 0]

    per_class: Dict[int, float] = {}
    for lab in labels:
        per_class[lab] = overlap.GetDiceCoefficient(int(lab))

    print(f"Per class dice: {per_class}")

    def macro_dice(per_class_dice: Dict[int, float]) -> float:
        return float(np.mean(list(per_class_dice.values()))) if per_class_dice else 1.0

    dice = macro_dice(per_class)
    return dice


@app.post("/dice-score")
async def calculate_dice(
    file: UploadFile = File(...),
    name: str = Form(...)
):
    if not file.filename.endswith(".nii.gz"):
        raise HTTPException(status_code=400, detail="File must be a .nii.gz file")

    if not REFERENCE_FILE.exists():
        raise HTTPException(status_code=500, detail="Reference file not found on server")

    # Save uploaded file temporarily
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".nii.gz") as tmp_file:
            contents = await file.read()
            tmp_file.write(contents)
            tmp_file_path = tmp_file.name

        try:
            pred_img = sitk.ReadImage(tmp_file_path)
            ref_img = sitk.ReadImage(str(REFERENCE_FILE))
            
            #check if shapes match
            if pred_img.GetSize() != ref_img.GetSize():
                raise HTTPException(status_code=400, detail="Uploaded image shape does not match reference image shape")

            dice_score = calculate_dice_score(pred_img, ref_img)

            result = {
                "score": dice_score,
                "name": name,
            }

            results_file = RESULTS_FILE

            if results_file.exists():
                with open(results_file, "r") as f:
                    results = json.load(f)
            else:
                results = []

            results.append(result)

            with open(results_file, "w") as f:
                json.dump(results, f, indent=2)

            return JSONResponse(content=result, status_code=200)

        finally:
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)

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
