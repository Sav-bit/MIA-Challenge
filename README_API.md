# MIA Challenge - Dice Score API

A Django server-side application that calculates Dice scores between uploaded NIfTI (.nii.gz) files and a reference file.

## Features

- POST endpoint for uploading .nii.gz files
- Automatic Dice score calculation
- Results stored in JSON format
- Support for multiple group submissions

## Setup

### Using Conda

1. Create the environment:
```bash
conda env create -f environment.yml
conda activate mia-challenge
```

2. Run migrations:
```bash
python manage.py migrate
```

3. Start the server:
```bash
python manage.py runserver
```

## API Usage

### Endpoint

**POST** `/api/dice/calculate/`

### Parameters

- `file` (required): NIfTI file (.nii.gz format)
- `name` (required): Group name identifier

### Example Request

```bash
curl -X POST http://localhost:8000/api/dice/calculate/ \
  -F "file=@path/to/your/file.nii.gz" \
  -F "name=group_name"
```

### Example Response

```json
{
  "score": 0.8523,
  "name": "group_name"
}
```

### Error Responses

- `400`: Missing file or name, invalid file format, or shape mismatch
- `500`: Server error or missing reference file

## Results Storage

Results are automatically saved to `results/results.json` in the following format:

```json
[
  {
    "score": 0.8523,
    "name": "group_name_1"
  },
  {
    "score": 0.7654,
    "name": "group_name_2"
  }
]
```

## Reference File

The server compares uploaded files against a reference file located at `reference/reference.nii.gz`. Make sure this file exists before using the API.

## Dependencies

- Django 4.2
- numpy 1.24
- nibabel 5.1
- scipy 1.11
- djangorestframework 3.14.0

All dependencies are listed in `environment.yml`.

## Dice Score Calculation

The Dice score is calculated using the formula:

```
Dice = 2 * |A ∩ B| / (|A| + |B|)
```

Where A is the uploaded segmentation and B is the reference segmentation.
