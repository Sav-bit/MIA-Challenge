import json
import os
import tempfile
from pathlib import Path

import nibabel as nib
import numpy as np
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods


def calculate_dice_score(pred_array, ref_array):
    """
    Calculate Dice score between two binary arrays.
    
    Dice score = 2 * |A ∩ B| / (|A| + |B|)
    """
    # Flatten arrays
    pred_flat = pred_array.flatten()
    ref_flat = ref_array.flatten()
    
    # Calculate intersection and union
    intersection = np.sum(pred_flat * ref_flat)
    sum_pred = np.sum(pred_flat)
    sum_ref = np.sum(ref_flat)
    
    # Handle edge case where both arrays are empty
    if sum_pred + sum_ref == 0:
        return 1.0
    
    # Calculate Dice score
    dice = (2.0 * intersection) / (sum_pred + sum_ref)
    return float(dice)


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
            pred_img = nib.load(tmp_file_path)
            ref_img = nib.load(str(reference_path))
            
            # Get data arrays
            pred_data = pred_img.get_fdata()
            ref_data = ref_img.get_fdata()
            
            # Check if shapes match
            if pred_data.shape != ref_data.shape:
                return JsonResponse({
                    'error': f'Shape mismatch: uploaded {pred_data.shape} vs reference {ref_data.shape}'
                }, status=400)
            
            # Calculate Dice score
            dice_score = calculate_dice_score(pred_data, ref_data)
            
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
        return JsonResponse({'error': str(e)}, status=500)
