# MIA-Challenge

Challenge for the Deep Learning Exercise of **Medical Image Analysis**

This repository contains a lightweight FastAPI server that evaluates segmentation results submitted by participants.

The server:

- Accepts predictions as a **single `.npz` file**
- Compares them against **23 ground-truth slices**
- Computes a **macro Dice score per subject**
- Outputs the **mean Dice** across all subjects
- Stores results in a persistent leaderboard
- Displays a **web podium** with animations 🎉

---

## 🚀 How to Run the Evaluation Server

The server runs entirely in Docker — **you do NOT need Python installed**.

### 1. Clone this repository

```bash
git clone https://github.com/Sav-bit/MIA-Challenge.git
cd MIA-Challenge
```

### 2. Start the server using Docker Compose

```bash
docker compose up --build
```

This will:

- Build the FastAPI application  
- Load the ground truth `test_data_reference.npz`  
- Create a **Docker volume** to persist `results.json`  
- Start the server on **<http://localhost:8000>**

---

## 📤 Submitting Your Segmentation

The evaluation endpoint is:

```
POST http://localhost:8000/dice-score
```

It expects:

| Field | Type | Description |
|-------|------|-------------|
| `file` | `.npz` file | Your segmentation predictions |
| `name` | string | Team or group name |

### Example using curl

```bash
curl -X POST "http://localhost:8000/dice-score"   -F "file=@submission.npz"   -F "name=Team7"
```

---

## 📦 Submission Format (`.npz`)

Your submission must be **one compressed NumPy archive** containing one prediction per subject.

Example:

```python
np.savez_compressed(
    "submission.npz",
    subj-01=pred_subj01,
    subj-02=pred_subj02,
    ...
    subj-23=pred_subj23,
)
```

---

## 🧮 Scoring

For each subject:

1. Compute Dice per class (`label != 0`)
2. Take the mean across classes → **macro Dice**
3. Then average macro Dice across all 23 subjects

If a team submits multiple times with the same name, the **best score** is shown on the podium.

---

## 🏆 Viewing the Podium

Open:

```
http://localhost:8000/podium
```

Top 3 are shown on a podium with suspense animation + confetti 🎉  
Others appear in a leaderboard table.

---

### Credits

- The podium was adapted from this code-pen by [Thomas Scourneau](https://codepen.io/k0y0te/pen/JwjOKY)
- The confetti are made with [canvas-confetti](https://www.kirilv.com/canvas-confetti/)
