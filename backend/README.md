# Filmoid Backend

FastAPI backend for Filmoid. This service:

- Handles **authentication** (signup/login/logout) using JWTs stored in **HttpOnly cookies**
- Stores **users**, **persistent ratings**, and **recommendation sessions** in PostgreSQL (Supabase)
- Exposes a recommendations API that uses a **Surprise SVD** model when available, with a **TMDB-based fallback**

## Backend architecture

```mermaid
flowchart TD
  B[Browser] --> FE[React + Vite (Vercel)]
  FE --> API[FastAPI (Hugging Face Spaces)]
  API --> DB[(Supabase PostgreSQL)]
```

- **Framework:** FastAPI
- **ORM:** SQLAlchemy
- **Database:** PostgreSQL (Supabase)
- **Auth:** JWT (`python-jose`) + password hashing (`passlib[bcrypt]`)
- **Recommender:** `scikit-surprise` SVD + NumPy; fallback recommender uses TMDB API requests

Key modules:

- `app/main.py`: FastAPI app, CORS, recommendations endpoints, and recommender implementation
- `app/auth.py`: JWT cookie auth helpers + dependencies
- `app/models.py`: SQLAlchemy models
- `app/crud.py`: DB helper functions
- `app/routers/auth.py`: `/api/auth/*` endpoints
- `app/routers/users.py`: `/api/users/*` endpoints

## API overview

Base URL (local): `http://localhost:8000`

### Health

- `GET /health` → `{ "status": "ok" }`

### Authentication endpoints

- `POST /api/auth/signup`
  - Body (JSON): `{ "username": string, "email": string, "password": string }`
  - Creates a user.

- `POST /api/auth/login`
  - Body (`application/x-www-form-urlencoded`): `username`, `password`
  - Accepts **username or email** in the `username` field.
  - On success, sets an **HttpOnly cookie** containing a JWT.

- `POST /api/auth/logout`
  - Clears the auth cookie.

### Recommendation endpoints

- `POST /api/recommendations`
  - Body (JSON):
    - `tmdbApiKey`: TMDB v3 API key
    - `ratings`: array of `{ tmdbId: number, rating: number }`
    - `topN`: number (default 10)
  - Requires at least **5** rated movies.
  - Returns: `{ sessionId, recommendations: MovieOut[] }`
  - Creates a `RecommendationSession` record in the database.
    - If the caller is authenticated, the session is linked to the user.

- `GET /api/recommendations/{session_id}`
  - Returns a previously saved recommendation session.

### Ratings endpoints (authenticated)

- `POST /api/users/me/ratings`
  - Upsert a rating for the current user.
  - Body (JSON):
    - `tmdb_id`: number
    - `movie_title`: string
    - `poster_path`: string | null
    - `release_date`: string | null
    - `rating`: number (1–10)

- `GET /api/users/me/ratings`
  - Lists the current user’s most recent ratings (newest updated first).

- `DELETE /api/users/me/ratings/{tmdb_id}`
  - Deletes the current user’s rating for the given TMDB id.

### User endpoints (authenticated)

- `GET /api/users/me`
  - Returns the authenticated user.

- `GET /api/users/me/recommendations`
  - Lists saved recommendation sessions for the current user.

## Database models

Defined in `app/models.py`:

- `User`
  - `id` (UUID)
  - `username` (case-insensitive)
  - `email` (case-insensitive)
  - `password_hash`
  - `created_at`

- `UserRating`
  - `user_id` (FK → users)
  - `tmdb_id` (int)
  - `movie_title`, `poster_path`, `release_date` (snapshot metadata)
  - `rating` (float)
  - `created_at`, `updated_at`

- `RecommendationSession`
  - `id` (UUID)
  - `user_id` (nullable FK → users)
  - `recommendations` (JSON list)
  - `created_at`

## Environment variables

The backend reads env vars via `python-dotenv` (see `backend/.env`).

Required:

- `DATABASE_URL`: PostgreSQL connection string (Supabase)
- `SECRET_KEY`: JWT signing key

Optional:

- `ALLOWED_ORIGINS`: comma-separated list for CORS (default `http://localhost:5173`)
- `FILMOID_RECOMMENDER`: `auto` (default), `svd`, or `tmdb`

## Running locally

```bash
cd backend
python3 -m pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Deployment notes (Hugging Face Spaces)

- The repo `Dockerfile` builds and runs this backend on port `7860`.
- Configure **Space secrets**:
  - `DATABASE_URL`
  - `SECRET_KEY`
- Ensure CORS origins match your deployed frontend domain (set `ALLOWED_ORIGINS`).

## Notes about the SVD model

- The backend looks for `backend/models/svd_model.pkl`.
- When available, recommendations are generated using the SVD model.
- If SVD is unavailable (missing model or dependencies), the backend automatically falls back to a TMDB-based heuristic.

## Troubleshooting

### 401 / Not authenticated

- Confirm the frontend uses `credentials: 'include'` for authenticated requests.
- For local dev, ensure the API is reachable at the base URL used by the frontend (`VITE_API_BASE_URL`).

### CORS errors in the browser

- Set `ALLOWED_ORIGINS` to include your frontend origin(s), comma-separated.

### Recommendations fall back to TMDB unexpectedly

- Ensure `backend/models/svd_model.pkl` exists and is a real model artifact (not an LFS pointer).
- Ensure backend dependencies are installed (`scikit-surprise`, `numpy`).
