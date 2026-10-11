# PulseDesk Content Intelligence

A normal-user news/content intelligence website built with Flask and SQLite.

## Run in VS Code

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000`

Demo login: `admin` / `admin123`

## What changed
- Removed algorithm names from the normal user interface.
- Replaced the lab-style screens with a normal content workspace.
- Added a live-style story stream with automatic refresh every 8 seconds.
- Added smart search with automatic typo suggestions.
- Added related-story and repeated-coverage detection.
- Added trending topic grouping.
- Added a review queue with status updates.
- Added a form to publish a new story directly into the live stream.
- Kept the text matching, similarity, grouping and workload logic in the backend so the algorithms power features instead of being displayed as the product.

Note: the bundled stories are local demo data. The live-style interface refreshes the application's content stream; it does not claim to fetch external news from the internet.
