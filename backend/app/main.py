from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


class RatingIn(BaseModel):
    tmdbId: int = Field(..., ge=1)
    rating: float = Field(..., ge=1, le=10)


class RecommendRequest(BaseModel):
    tmdbApiKey: str = Field(..., min_length=5)
    ratings: List[RatingIn] = Field(default_factory=list)
    topN: int = Field(10, ge=1, le=50)


class MovieOut(BaseModel):
    id: int
    title: str
    poster_path: Optional[str] = None


class RecommendResponse(BaseModel):
    recommendations: List[MovieOut]


@dataclass(frozen=True)
class ScoredMovie:
    movie_id: int
    score: float
    title: str
    poster_path: Optional[str]


app = FastAPI(title="Filmoid API", version="0.1.0")

# Local dev: allow the Vite dev server to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


def _tmdb_get(url: str, api_key: str, params: Optional[Dict[str, str]] = None) -> Dict:
    p = {"api_key": api_key, "language": "en-US"}
    if params:
        p.update(params)

    res = requests.get(url, params=p, headers={"accept": "application/json"}, timeout=20)
    if res.status_code == 401:
        raise HTTPException(status_code=401, detail="TMDB API key invalid or unauthorized")
    if not res.ok:
        raise HTTPException(status_code=502, detail=f"TMDB request failed ({res.status_code})")
    return res.json()


def _blend_tmdb_recommendations(
    api_key: str,
    rated: List[Tuple[int, float]],
    top_n: int,
) -> List[MovieOut]:
    """A local-dev recommender.

    This is NOT your Surprise SVD model yet.
    It blends TMDB's per-movie recommendations weighted by the user's ratings,
    so the frontend flow works end-to-end while you wire in SVD.
    """

    rated_ids = {movie_id for movie_id, _ in rated}
    scores: Dict[int, ScoredMovie] = {}

    for movie_id, rating in rated:
        url = f"https://api.themoviedb.org/3/movie/{movie_id}/recommendations"
        payload = _tmdb_get(url, api_key, params={"page": "1"})
        results = payload.get("results") or []

        # Weight by rating and by rank (higher-ranked TMDB recs count more)
        for rank, m in enumerate(results[:50], start=1):
            rec_id = int(m.get("id"))
            if rec_id in rated_ids:
                continue

            title = (m.get("title") or m.get("name") or "").strip() or f"{rec_id}"
            poster_path = m.get("poster_path")

            # simple scoring: higher user rating & higher TMDB rank => higher score
            contribution = float(rating) * (1.0 / float(rank))

            if rec_id in scores:
                prev = scores[rec_id]
                scores[rec_id] = ScoredMovie(
                    movie_id=rec_id,
                    score=prev.score + contribution,
                    title=prev.title or title,
                    poster_path=prev.poster_path or poster_path,
                )
            else:
                scores[rec_id] = ScoredMovie(
                    movie_id=rec_id,
                    score=contribution,
                    title=title,
                    poster_path=poster_path,
                )

    ranked = sorted(scores.values(), key=lambda x: x.score, reverse=True)
    return [MovieOut(id=m.movie_id, title=m.title, poster_path=m.poster_path) for m in ranked[:top_n]]


@app.post("/api/recommendations", response_model=RecommendResponse)
def recommend(req: RecommendRequest) -> RecommendResponse:
    if len(req.ratings) < 5:
        raise HTTPException(status_code=400, detail="Need at least 5 rated movies")

    rated_pairs = [(r.tmdbId, float(r.rating)) for r in req.ratings]

    # Local-dev implementation: TMDB blend.
    recs = _blend_tmdb_recommendations(req.tmdbApiKey, rated_pairs, req.topN)
    return RecommendResponse(recommendations=recs)
