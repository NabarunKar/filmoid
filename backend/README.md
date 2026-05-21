# Filmoid Backend (Local Dev)

This is a minimal FastAPI backend used by the Vite frontend during local development.

## Run

```bash
cd backend
python3 -m pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Health check:
- http://localhost:8000/health

## Endpoint

- `POST /api/recommendations`
  - Requires at least 5 rated movies.
  - Default behavior (`FILMOID_RECOMMENDER=auto`): uses the Surprise SVD model from `backend/models/svd_model.pkl` when available, otherwise falls back to a TMDB-blend heuristic.
  - Force modes:
    - `FILMOID_RECOMMENDER=svd` (error if SVD is unavailable)
    - `FILMOID_RECOMMENDER=tmdb` (always use TMDB-blend)

### Optional: Deterministic TMDB ↔ Slug Mapping

If your SVD model was trained on Letterboxd-style slugs (e.g. `mank`) instead of TMDB numeric IDs, you can make the mapping foolproof by providing:

- `backend/models/tmdb_to_slug.csv` with columns: `tmdb_id,slug`

When present, the backend will use this file to map:
- user-rated TMDB IDs → SVD item IDs
- recommended slugs → TMDB IDs (avoids ambiguous TMDB search)

### Optional: Letterboxd Redirect Bridge

You can also enable a best-effort live mapping via `https://letterboxd.com/tmdb/<id>` redirects:

- `FILMOID_USE_LETTERBOXD_BRIDGE=1`

Note: this may return `403 Forbidden` from server-side requests in some environments.
