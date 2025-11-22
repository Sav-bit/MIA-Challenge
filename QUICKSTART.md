# Quick Start Guide

## Setup

### 1. Create Conda Environment

```bash
conda env create -f environment.yml
conda activate mia-challenge
```

### 2. Initialize Database

```bash
python manage.py migrate
```

### 3. Start Server

```bash
python manage.py runserver
```

The server will start at `http://localhost:8000`

## Usage

### Submit a file for Dice score calculation

```bash
curl -X POST http://localhost:8000/api/dice/calculate/ \
  -F "file=@your_file.nii.gz" \
  -F "name=your_group_name"
```

### Example Response

```json
{
  "score": 0.8523,
  "name": "your_group_name"
}
```

## Testing

Run the automated test script:

```bash
bash test_api.sh
```

## Results

All results are automatically saved to `results/results.json`:

```json
[
  {
    "score": 0.8523,
    "name": "group_1"
  },
  {
    "score": 0.7654,
    "name": "group_2"
  }
]
```

## Reference File

The server compares submissions against `reference/reference.nii.gz`.
Replace this file with your actual reference segmentation.

## Project Structure

```
MIA-Challenge/
├── environment.yml          # Conda environment configuration
├── manage.py               # Django management script
├── mia_challenge/          # Django project settings
├── dice_score/             # Django app with API
│   ├── views.py           # API endpoint implementation
│   └── urls.py            # URL routing
├── reference/              # Reference NIfTI files
│   └── reference.nii.gz   # Reference segmentation
├── test_api.sh            # Automated test script
├── README_API.md          # Detailed API documentation
└── QUICKSTART.md          # This file
```

## Dependencies

- Django 4.2
- numpy 1.24
- nibabel 5.1
- scipy 1.11
- djangorestframework 3.14.0

For more details, see [README_API.md](README_API.md)
