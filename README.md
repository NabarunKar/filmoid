# Filmoid — Recommendation-Only

This branch contains only the movie recommendation web app (ratings-based recommendations).

## What’s included

- `frontend/`: Vite + React UI that lets you search TMDB, select movies, rate them 1–10, and request recommendations.
- `backend/`: FastAPI endpoint `POST /api/recommendations`.
	- Tries to use a Surprise SVD model from `backend/models/svd_model.pkl` when available.
	- Falls back to a TMDB-weighted blend so the UI works end-to-end without an SVD artifact.
- `Resources/`: kept intentionally for future work.

## Local dev

Backend:

```bash
cd backend
python3 -m pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Environment variables (frontend):

- `VITE_TMDB_V3` (required): TMDB v3 API key
- `VITE_API_BASE_URL` (optional): defaults to `http://localhost:8000`