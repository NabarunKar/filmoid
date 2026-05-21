from __future__ import annotations

from dataclasses import dataclass
import logging
import os
from functools import lru_cache
from pathlib import Path
import re
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

# Use uvicorn's logger so messages reliably show up in the server console.
logger = logging.getLogger("uvicorn.error")
_SVD_MODEL_PATH = Path(__file__).resolve().parents[1] / "models" / "svd_model.pkl"
_TMDB_TO_SLUG_PATH = Path(__file__).resolve().parents[1] / "models" / "tmdb_to_slug.csv"


@lru_cache(maxsize=1)
def _load_tmdb_slug_map() -> Tuple[Dict[int, str], Dict[str, int]]:
    """Load an optional mapping file: backend/models/tmdb_to_slug.csv

    Expected columns (header optional):
      tmdb_id,slug

    Returns:
      (tmdb_to_slug, slug_to_tmdb)
    """

    if not _TMDB_TO_SLUG_PATH.exists():
        return ({}, {})

    tmdb_to_slug: Dict[int, str] = {}
    slug_to_tmdb: Dict[str, int] = {}
    try:
        text = _TMDB_TO_SLUG_PATH.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ({}, {})

    for line in text.splitlines():
        row = line.strip()
        if not row or row.startswith("#"):
            continue
        parts = [p.strip() for p in row.split(",", 1)]
        if len(parts) != 2:
            continue
        left, right = parts
        if left.lower() in {"tmdb_id", "tmdbid", "tmdb"}:
            continue
        tmdb_id = _coerce_int(left)
        slug = (right or "").strip().strip("/").lower()
        if tmdb_id is None or not slug:
            continue
        tmdb_to_slug[tmdb_id] = slug
        # Only set reverse if not already present.
        slug_to_tmdb.setdefault(slug, tmdb_id)

    return (tmdb_to_slug, slug_to_tmdb)

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


def _letterboxd_headers() -> Dict[str, str]:
    # Letterboxd may reject "empty" clients; provide a benign UA.
    return {
        "user-agent": "FilmoidLocalDev/0.1 (+https://localhost)",
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }


def _parse_letterboxd_film_slug_from_url(url: str) -> Optional[str]:
    # Expected final URL format: https://letterboxd.com/film/<slug>/
    m = re.search(r"https?://letterboxd\.com/film/([^/]+)/?", url)
    if not m:
        return None
    slug = (m.group(1) or "").strip().lower()
    return slug or None


@lru_cache(maxsize=10_000)
def _letterboxd_slug_from_tmdb_id(tmdb_id: int) -> Optional[str]:
    """Resolve a TMDB movie id to a Letterboxd film slug via redirect.

    https://letterboxd.com/tmdb/<TMDB_ID> redirects to https://letterboxd.com/film/<slug>/
    """

    url = f"https://letterboxd.com/tmdb/{tmdb_id}"
    try:
        res = requests.get(
            url,
            headers=_letterboxd_headers(),
            timeout=15,
            allow_redirects=True,
        )
    except Exception:
        return None

    if not res.ok:
        return None

    return _parse_letterboxd_film_slug_from_url(res.url)


@lru_cache(maxsize=1)
def _load_svd_algo():
    """Best-effort load of the Surprise SVD model.

    Returns the Surprise algo instance on success, else None.
    """

    if not _SVD_MODEL_PATH.exists():
        return None

    try:
        from surprise.dump import load as surprise_load  # type: ignore
    except Exception:
        return None

    try:
        predictions, algo = surprise_load(str(_SVD_MODEL_PATH))
        _ = predictions  # unused
        return algo
    except Exception:
        # Some users may have serialized the algo via joblib/pickle directly.
        try:
            import joblib  # type: ignore

            return joblib.load(_SVD_MODEL_PATH)
        except Exception:
            return None


def _try_inner_iid(trainset, raw_iid: object) -> Optional[int]:
    for candidate in (raw_iid, str(raw_iid)):
        try:
            return int(trainset.to_inner_iid(candidate))
        except Exception:
            continue
    return None


def _coerce_int(raw: object) -> Optional[int]:
    try:
        # Accept numeric strings too.
        value = int(raw)
        return value if value > 0 else None
    except Exception:
        try:
            value = int(float(str(raw).strip()))
            return value if value > 0 else None
        except Exception:
            return None


def _slugify_title(title: str) -> str:
    s = title.strip().lower()
    # Replace & with "and" to better match common slugs.
    s = s.replace("&", " and ")
    # Keep alphanumerics and spaces, then hyphenate.
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"[\s_-]+", "-", s)
    s = re.sub(r"-+", "-", s)
    return s.strip("-")


def _tmdb_title_and_year(api_key: str, tmdb_id: int) -> Tuple[str, Optional[int]]:
    details = _tmdb_get(f"https://api.themoviedb.org/3/movie/{tmdb_id}", api_key)
    title = (details.get("title") or details.get("name") or "").strip()
    year: Optional[int] = None
    release_date = (details.get("release_date") or "").strip()
    if release_date:
        try:
            year = int(release_date.split("-", 1)[0])
        except Exception:
            year = None
    return (title or str(tmdb_id), year)


def _trainset_looks_numeric(trainset) -> bool:
    # Heuristic: if most sample item IDs are numeric, treat them as TMDB IDs.
    raw2inner = getattr(trainset, "_raw2inner_id_items", None)
    if not isinstance(raw2inner, dict) or not raw2inner:
        return False
    sample: List[object] = []
    for k in raw2inner.keys():
        sample.append(k)
        if len(sample) >= 25:
            break
    numeric = sum(1 for x in sample if _coerce_int(x) is not None)
    return numeric >= max(1, int(0.8 * len(sample)))


def _tmdb_to_model_raw_iid(api_key: str, tmdb_id: int, trainset) -> Optional[str]:
    tmdb_to_slug, _slug_to_tmdb = _load_tmdb_slug_map()
    mapped = tmdb_to_slug.get(int(tmdb_id))
    if mapped and _try_inner_iid(trainset, mapped) is not None:
        return mapped

    # Optional: Prefer Letterboxd redirect mapping when enabled.
    # Note: may return 403 in some environments due to bot protection.
    if (os.getenv("FILMOID_USE_LETTERBOXD_BRIDGE") or "").strip() in {"1", "true", "yes"}:
        lb_slug = _letterboxd_slug_from_tmdb_id(int(tmdb_id))
        if lb_slug and _try_inner_iid(trainset, lb_slug) is not None:
            return lb_slug

    # Fallback: heuristic slug candidates from TMDB title/year.
    title, year = _tmdb_title_and_year(api_key, tmdb_id)
    base = _slugify_title(title)
    candidates: List[str] = []
    if base:
        candidates.append(base)
        if year:
            candidates.append(f"{base}-{year}")
        # Common alternates.
        if base.startswith("the-"):
            candidates.append(base[len("the-"):])
            if year:
                candidates.append(f"{base[len('the-'):]}-{year}")

    for slug in candidates:
        if _try_inner_iid(trainset, slug) is not None:
            return slug

    return None


def _tmdb_search_movie(api_key: str, query: str, year: Optional[int] = None) -> Optional[MovieOut]:
    url = "https://api.themoviedb.org/3/search/movie"
    params: Dict[str, str] = {
        "query": query,
        "include_adult": "false",
        "language": "en-US",
        "page": "1",
    }
    if year:
        params["year"] = str(year)

    payload = _tmdb_get(url, api_key, params=params)
    results = payload.get("results") or []
    if not results:
        return None

    m = results[0]
    tmdb_id = _coerce_int(m.get("id"))
    if tmdb_id is None:
        return None

    title = (m.get("title") or m.get("name") or "").strip() or str(tmdb_id)
    poster_path = m.get("poster_path")
    return MovieOut(id=tmdb_id, title=title, poster_path=poster_path)


def _slug_to_tmdb_movie(api_key: str, slug: str) -> Optional[MovieOut]:
    s = slug.strip().lower()
    year: Optional[int] = None
    m = re.match(r"^(.*?)-(\d{4})$", s)
    if m:
        s = m.group(1)
        try:
            year = int(m.group(2))
        except Exception:
            year = None

    _tmdb_to_slug, slug_to_tmdb = _load_tmdb_slug_map()
    tmdb_id = slug_to_tmdb.get(s)
    if tmdb_id is not None:
        try:
            details = _tmdb_get(f"https://api.themoviedb.org/3/movie/{tmdb_id}", api_key)
        except HTTPException:
            return None
        title = (details.get("title") or details.get("name") or "").strip() or str(tmdb_id)
        poster_path = details.get("poster_path")
        return MovieOut(id=tmdb_id, title=title, poster_path=poster_path)

    query = s.replace("-", " ").strip()
    if not query:
        return None
    return _tmdb_search_movie(api_key, query=query, year=year)


def _svd_recommendations(
    api_key: str,
    rated: List[Tuple[int, float]],
    top_n: int,
) -> List[MovieOut]:
    """Generate recommendations from the saved Surprise SVD model.

    This performs a lightweight "fold-in" to compute a temporary user vector
    from the provided ratings, without retraining the global model.

    Requires:
    - `backend/models/svd_model.pkl` to exist
    - `scikit-surprise` to be installed
        - If model item IDs are not TMDB IDs, we use TMDB title/year heuristics
            to bridge TMDB <-> model IDs.
    """

    algo = _load_svd_algo()
    if algo is None:
        raise RuntimeError("SVD model not available (missing deps or model file)")

    trainset = getattr(algo, "trainset", None)
    if trainset is None:
        raise RuntimeError("SVD model missing trainset; cannot enumerate items")

    try:
        import numpy as np  # type: ignore
    except Exception as e:
        raise RuntimeError("numpy is required for SVD recommendations") from e

    qi = np.asarray(getattr(algo, "qi", None))
    bi = np.asarray(getattr(algo, "bi", None))
    # Surprise stores the global mean on the trainset; some dumps won't have
    # algo.global_mean at all.
    mu_raw = getattr(trainset, "global_mean", None)
    if mu_raw is None:
        mu_raw = getattr(algo, "global_mean", 0.0)
    try:
        mu = float(mu_raw)
    except Exception:
        mu = 0.0

    if qi.ndim != 2 or bi.ndim != 1 or qi.shape[0] != bi.shape[0]:
        raise RuntimeError("Unexpected SVD parameter shapes (qi/bi)")

    numeric_items = _trainset_looks_numeric(trainset)

    rated_tmdb_ids = {movie_id for movie_id, _ in rated}

    # Map user-rated TMDB IDs to model inner IDs. Models may be trained on:
    # - numeric TMDB IDs
    # - string slugs (e.g., Letterboxd)
    rated_inner: List[Tuple[int, float]] = []
    rated_inner_set: set[int] = set()
    mapping_misses: List[str] = []

    if numeric_items:
        for tmdb_id, rating in rated:
            inner = _try_inner_iid(trainset, tmdb_id)
            if inner is None:
                mapping_misses.append(f"tmdbId={tmdb_id} (not in model)")
                continue
            rated_inner.append((inner, float(rating)))
            rated_inner_set.add(inner)
    else:
        for tmdb_id, rating in rated:
            slug = _tmdb_to_model_raw_iid(api_key, tmdb_id, trainset)
            if not slug:
                title, year = _tmdb_title_and_year(api_key, tmdb_id)
                lb_slug = None
                if (os.getenv("FILMOID_USE_LETTERBOXD_BRIDGE") or "").strip() in {"1", "true", "yes"}:
                    lb_slug = _letterboxd_slug_from_tmdb_id(int(tmdb_id))
                mapping_misses.append(
                    f"tmdbId={tmdb_id} title={title!r} year={year} letterboxdSlug={lb_slug!r}"
                )
                continue
            inner = _try_inner_iid(trainset, slug)
            if inner is None:
                title, year = _tmdb_title_and_year(api_key, tmdb_id)
                mapping_misses.append(
                    f"tmdbId={tmdb_id} title={title!r} year={year} mappedSlug={slug!r} (not in model)"
                )
                continue
            rated_inner.append((inner, float(rating)))
            rated_inner_set.add(inner)

    if mapping_misses:
        logger.info(
            "SVD mapping: mapped=%d/%d misses=%d. Examples: %s",
            len(rated_inner),
            len(rated),
            len(mapping_misses),
            "; ".join(mapping_misses[:5]),
        )

    # If we can't map enough rated movies into the model's item-space,
    # we can't meaningfully personalize.
    if len(rated_inner) < 5:
        raise RuntimeError(
            "Too few rated items exist in the SVD model item space (need >=5 mapped ratings). "
            + ("Mapping misses: " + "; ".join(mapping_misses[:5]) if mapping_misses else "")
        )

    # Fold-in: solve ridge regression for [b_u, p_u].
    n_factors = int(qi.shape[1])
    Q = np.vstack([qi[i] for i, _ in rated_inner])
    y = np.asarray([r - mu - float(bi[i]) for i, r in rated_inner], dtype=float)

    A = np.concatenate([np.ones((Q.shape[0], 1), dtype=float), Q], axis=1)
    # Some trained Surprise SVD dumps persist reg_all=None.
    reg_raw = getattr(algo, "reg_all", None)
    if reg_raw is None:
        reg_raw = 0.02
    reg = float(reg_raw)
    ATA = A.T @ A + reg * np.eye(1 + n_factors, dtype=float)
    ATy = A.T @ y
    x = np.linalg.solve(ATA, ATy)
    b_u = float(x[0])
    p_u = x[1:]

    # Score items (vectorized). If the model has a huge numeric-ID catalog,
    # prefer reranking a TMDB candidate pool for speed.
    n_items = int(qi.shape[0])
    top_raw_items: List[object] = []

    if numeric_items and n_items > 200_000:
        # Candidate pool from TMDB (same as the current heuristic), then rerank by SVD.
        candidates: Dict[int, float] = {}
        rated_ids = {movie_id for movie_id, _ in rated}
        for movie_id, _rating in rated:
            url = f"https://api.themoviedb.org/3/movie/{movie_id}/recommendations"
            payload = _tmdb_get(url, api_key, params={"page": "1"})
            results = payload.get("results") or []
            for m in results[:200]:
                rec_id = _coerce_int(m.get("id"))
                if rec_id is None or rec_id in rated_ids:
                    continue
                candidates[rec_id] = 0.0

        if not candidates:
            raise RuntimeError("No candidate items available to rerank")

        scored: List[Tuple[int, float]] = []
        for rec_id in candidates.keys():
            inner = _try_inner_iid(trainset, rec_id)
            if inner is None:
                continue
            est = mu + b_u + float(bi[inner]) + float(qi[inner] @ p_u)
            scored.append((rec_id, est))

        scored.sort(key=lambda t: t[1], reverse=True)
        top_raw_items = [movie_id for movie_id, _ in scored[: max(top_n * 3, top_n)]]
    else:
        scores = (mu + b_u) + bi + (qi @ p_u)
        if rated_inner_set:
            scores[list(rated_inner_set)] = -np.inf

        k = min(max(top_n * 3, top_n), n_items)
        top_inner = np.argpartition(scores, -k)[-k:]
        top_inner = top_inner[np.argsort(scores[top_inner])[::-1]]

        for inner in top_inner:
            top_raw_items.append(trainset.to_raw_iid(int(inner)))
            if len(top_raw_items) >= k:
                break

    # Hydrate top-N.
    movies: List[MovieOut] = []
    seen: set[int] = set()

    if numeric_items:
        for raw in top_raw_items:
            if len(movies) >= top_n:
                break
            tmdb_id = _coerce_int(raw)
            if tmdb_id is None:
                continue
            if tmdb_id in rated_tmdb_ids or tmdb_id in seen:
                continue
            seen.add(tmdb_id)
            try:
                details = _tmdb_get(f"https://api.themoviedb.org/3/movie/{tmdb_id}", api_key)
            except HTTPException:
                continue
            title = (details.get("title") or details.get("name") or "").strip() or str(tmdb_id)
            poster_path = details.get("poster_path")
            movies.append(MovieOut(id=tmdb_id, title=title, poster_path=poster_path))
        return movies

    # Slug-trained model: convert slugs to TMDB movies via TMDB search.
    for slug in [str(s) for s in top_raw_items]:
        if len(movies) >= top_n:
            break
        m = _slug_to_tmdb_movie(api_key, slug)
        if not m:
            continue
        if m.id in rated_tmdb_ids or m.id in seen:
            continue
        seen.add(m.id)
        movies.append(m)

    return movies


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

    mode = (os.getenv("FILMOID_RECOMMENDER") or "auto").strip().lower()

    if mode in {"auto", "svd"}:
        try:
            recs = _svd_recommendations(req.tmdbApiKey, rated_pairs, req.topN)
            logger.info("Using SVD recommender (%d results)", len(recs))
            return RecommendResponse(recommendations=recs)
        except Exception as e:
            logger.warning("SVD recommender unavailable; falling back (%s)", e)
            if mode == "svd":
                raise HTTPException(
                    status_code=500,
                    detail=(
                        "SVD recommender is enabled but unavailable. "
                        "Ensure scikit-surprise + numpy are installed and backend/models/svd_model.pkl "
                        "is readable. If the model uses non-TMDB item IDs (e.g., slugs), "
                        "the backend will rely on TMDB title/search heuristics to bridge IDs."
                    ),
                )

    # Fallback: TMDB blend heuristic.
    recs = _blend_tmdb_recommendations(req.tmdbApiKey, rated_pairs, req.topN)
    logger.info("Using TMDB-blend recommender (%d results)", len(recs))
    return RecommendResponse(recommendations=recs)
