# Filmoid Backend (Local Dev)

This is a minimal FastAPI backend used by the Vite frontend during local development.

## Run

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Health check:
- http://localhost:8000/health

## Endpoint

- `POST /api/recommendations`
  - Requires at least 5 rated movies.
  - Current implementation blends TMDB recommendations (so the UI works end-to-end).
  - Later you can swap in the Surprise SVD model behind the same endpoint.
