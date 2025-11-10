import json
import logging
import os
import tempfile
from pathlib import Path

import nibabel as nib
import numpy as np
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import SimpleITK as sitk

logger = logging.getLogger(__name__)


def calculate_dice_score(prediction : sitk.Image, reference : sitk.Image) -> float:
    overlap = sitk.LabelOverlapMeasuresImageFilter()
    overlap.Execute(reference, prediction)
    
    ref = sitk.GetArrayViewFromImage(reference)
    pred = sitk.GetArrayViewFromImage(prediction)

    labels = sorted(set(ref.ravel()) | set(pred.ravel()))
    labels = [lab for lab in labels if lab != 0]

    per_class = {}
    for lab in labels:
        per_class[lab] = overlap.GetDiceCoefficient(int(lab))

    print(f"Per class dice: {per_class}")

    def macro_dice(per_class_dice):
        return float(np.mean(list(per_class_dice.values()))) if per_class_dice else 1.0
    
    dice = macro_dice(per_class)
    
    return dice

@csrf_exempt
@require_http_methods(["POST"])
def calculate_dice(request):
    """
    POST endpoint to calculate Dice score.
    
    Expects:
    - file: nii.gz file
    - name: group name
    
    Returns:
    - JSON response with dice score
    """
    try:
        # Get uploaded file and name
        if 'file' not in request.FILES:
            return JsonResponse({'error': 'No file provided'}, status=400)
        
        if 'name' not in request.POST:
            return JsonResponse({'error': 'No name provided'}, status=400)
        
        uploaded_file = request.FILES['file']
        group_name = request.POST['name']
        
        # Validate file extension
        if not uploaded_file.name.endswith('.nii.gz'):
            return JsonResponse({'error': 'File must be a .nii.gz file'}, status=400)
        
        # Check if reference file exists
        reference_path = settings.REFERENCE_FILE
        if not reference_path.exists():
            return JsonResponse({'error': 'Reference file not found on server'}, status=500)
        
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix='.nii.gz') as tmp_file:
            for chunk in uploaded_file.chunks():
                tmp_file.write(chunk)
            tmp_file_path = tmp_file.name
        
        try:
            # Load both NIfTI files
            pred_img = sitk.ReadImage(tmp_file_path)   
            ref_img = sitk.ReadImage(str(reference_path))
            
            
            dice_score = calculate_dice_score(pred_img, ref_img)
            
            # Prepare result
            result = {
                'score': dice_score,
                'name': group_name
            }
            
            # Save to JSON file
            results_dir = settings.RESULTS_DIR
            results_dir.mkdir(exist_ok=True)
            results_file = results_dir / 'results.json'
            
            # Read existing results or create new list
            if results_file.exists():
                with open(results_file, 'r') as f:
                    results = json.load(f)
            else:
                results = []
            
            # Append new result
            results.append(result)
            
            # Write back to file
            with open(results_file, 'w') as f:
                json.dump(results, f, indent=2)
            
            return JsonResponse(result, status=200)
            
        finally:
            # Clean up temporary file
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)
    
    except Exception as e:
        logger.error(f"Error calculating dice score: {str(e)}", exc_info=True)
        return JsonResponse({'error': 'An internal error occurred while processing the request'}, status=500)
