#!/usr/bin/env python3
"""Build a deterministic TMDB → Letterboxd-slug mapping from movie_data.csv.

Why:
- Your Surprise SVD model was trained on Letterboxd `movie_id` slugs.
- The web UI uses TMDB IDs for search/ratings.
- `backend/app/main.py` can consume `backend/models/tmdb_to_slug.csv` to bridge IDs reliably.

Input CSV:
- Must contain (at minimum) these columns (names may vary):
  - slug: `movie_id` (Letterboxd movie slug)
  - title: `movie_title`
  - year: `year_released`

Output:
- Writes `tmdb_id,slug` CSV (default: backend/models/tmdb_to_slug.csv)
 - Writes a separate review CSV for ambiguous/low-confidence rows (default: backend/models/tmdb_to_slug_review.csv)

Notes:
- Title/year matching is not perfect; this script uses TMDB search and a simple scoring heuristic.
- Consider running first with `--limit 2000` to validate quality/speed.
- For long runs, `--checkpoint-every N` prints durable lines in addition to the live progress bar.
- Throttling: `--max-rps 45` (default) caps TMDB HTTP requests/sec. Total runtime depends on requests per row (some rows may require 2 searches).
"""

from __future__ import annotations

import argparse
import csv
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
import json
import os
import sys
import threading
import time
from dataclasses import dataclass
from difflib import SequenceMatcher
from itertools import islice
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Tuple

import requests


TMDB_SEARCH_URL = "https://api.themoviedb.org/3/search/movie"


class RateLimiter:
    def __init__(self, max_per_sec: float) -> None:
        self._min_interval = 1.0 / float(max_per_sec) if max_per_sec and max_per_sec > 0 else 0.0
        self._next_allowed = time.monotonic()
        self._lock = threading.Lock()

    def wait(self) -> None:
        if self._min_interval <= 0:
            return
        with self._lock:
            now = time.monotonic()
            if now < self._next_allowed:
                time.sleep(self._next_allowed - now)
                now = time.monotonic()
            self._next_allowed = now + self._min_interval


def _coerce_int(x: object) -> Optional[int]:
    try:
        v = int(str(x).strip())
        return v if v > 0 else None
    except Exception:
        return None


def _norm_title(s: str) -> str:
    return " ".join("".join(ch.lower() if ch.isalnum() else " " for ch in s).split())


def _title_similarity(a: str, b: str) -> float:
    a2 = _norm_title(a)
    b2 = _norm_title(b)
    if not a2 or not b2:
        return 0.0
    return SequenceMatcher(None, a2, b2).ratio()


def _tmdb_get(
    session: requests.Session,
    api_key: str,
    url: str,
    params: Dict[str, str],
    limiter: RateLimiter,
    on_request: Optional[Callable[[], None]] = None,
) -> Dict:
    p = {"api_key": api_key, "language": "en-US"}
    p.update(params)

    # Simple resilience for long-running jobs.
    # TMDB may occasionally return 429 (rate limited) or transient 5xx; retry with backoff.
    max_attempts = 6
    last_status: Optional[int] = None
    for attempt in range(1, max_attempts + 1):
        limiter.wait()
        if on_request is not None:
            try:
                on_request()
            except Exception:
                pass

        res = session.get(url, params=p, headers={"accept": "application/json"}, timeout=20)
        last_status = res.status_code
        if res.status_code == 401:
            raise RuntimeError("TMDB API key invalid or unauthorized")

        if res.ok:
            return res.json()

        if res.status_code == 429 or res.status_code >= 500 or res.status_code == 408:
            if attempt >= max_attempts:
                break
            retry_after = res.headers.get("Retry-After")
            if retry_after:
                try:
                    wait_s = max(1.0, float(retry_after))
                except Exception:
                    wait_s = 1.0
            else:
                wait_s = min(60.0, 2.0 ** (attempt - 1))
            time.sleep(wait_s)
            continue

        # Non-retriable status.
        raise RuntimeError(f"TMDB request failed ({res.status_code})")

    raise RuntimeError(f"TMDB request failed ({last_status})")


@dataclass(frozen=True)
class MovieRow:
    slug: str
    title: str
    year: Optional[int]


@dataclass(frozen=True)
class Match:
    tmdb_id: int
    score: float
    tmdb_title: str
    tmdb_year: Optional[int]
    release_date: str
    popularity: float


def _detect_columns(fieldnames: Iterable[str]) -> Tuple[str, str, str]:
    cols = {c.strip().lower(): c for c in fieldnames if c}

    slug_col = cols.get("movie_id") or cols.get("slug") or cols.get("movie_slug")
    title_col = cols.get("movie_title") or cols.get("title") or cols.get("name")
    year_col = cols.get("year_released") or cols.get("year") or cols.get("release_year")

    if not slug_col or not title_col:
        raise RuntimeError(
            "Could not detect required columns. Need at least slug (movie_id) and title (movie_title)."
        )

    # year is optional
    return (slug_col, title_col, year_col or "")


def _iter_rows(csv_path: Path) -> Iterable[MovieRow]:
    with csv_path.open("r", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise RuntimeError("CSV has no header row")

        slug_col, title_col, year_col = _detect_columns(reader.fieldnames)

        for row in reader:
            slug = (row.get(slug_col) or "").strip().strip("/").lower()
            title = (row.get(title_col) or "").strip()
            if not slug or not title:
                continue

            year = _coerce_int(row.get(year_col)) if year_col else None
            yield MovieRow(slug=slug, title=title, year=year)


def _pick_best_tmdb_result(title: str, year: Optional[int], results: List[Dict]) -> Optional[Match]:
    best: Optional[Match] = None
    best_score = -1.0

    for m in results:
        tmdb_id = _coerce_int(m.get("id"))
        if tmdb_id is None:
            continue

        m_title = (m.get("title") or "").strip()
        m_orig = (m.get("original_title") or "").strip()
        release_date = (m.get("release_date") or "").strip()
        m_year = _coerce_int(release_date.split("-", 1)[0]) if release_date else None

        sim = max(_title_similarity(title, m_title), _title_similarity(title, m_orig))
        year_bonus = 0.0
        if year and m_year:
            if year == m_year:
                year_bonus = 0.25
            elif abs(year - m_year) == 1:
                year_bonus = 0.10

        pop = float(m.get("popularity") or 0.0)
        pop_bonus = min(pop / 2000.0, 0.10)

        score = sim + year_bonus + pop_bonus
        if score > best_score:
            best_score = score
            best = Match(
                tmdb_id=tmdb_id,
                score=float(score),
                tmdb_title=m_title or m_orig or "",
                tmdb_year=m_year,
                release_date=release_date,
                popularity=pop,
            )

    # Basic threshold to avoid obviously wrong matches.
    if best is not None and best_score >= 0.60:
        return best
    return None


def _resolve_tmdb_match(
    session: requests.Session,
    api_key: str,
    title: str,
    year: Optional[int],
    limiter: RateLimiter,
    on_request: Optional[Callable[[], None]] = None,
) -> Optional[Match]:
    # First attempt: constrain by year (when available)
    params = {
        "query": title,
        "include_adult": "false",
        "page": "1",
    }
    if year:
        params["year"] = str(year)

    payload = _tmdb_get(session, api_key, TMDB_SEARCH_URL, params=params, limiter=limiter, on_request=on_request)
    results = payload.get("results") or []

    if not results and year:
        # Fallback: search without year, then score by year.
        params2 = {
            "query": title,
            "include_adult": "false",
            "page": "1",
        }
        payload = _tmdb_get(session, api_key, TMDB_SEARCH_URL, params=params2, limiter=limiter, on_request=on_request)
        results = payload.get("results") or []

    if not results:
        return None

    return _pick_best_tmdb_result(title, year, results)


def _load_existing(out_path: Path) -> Dict[str, str]:
    if not out_path.exists():
        return {}
    existing: Dict[str, str] = {}
    with out_path.open("r", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tmdb_id = str(row.get("tmdb_id") or "").strip()
            slug = str(row.get("slug") or "").strip().lower()
            if tmdb_id and slug:
                existing[tmdb_id] = slug
    return existing


def _build_slug_index(tmdb_to_slug: Dict[str, str]) -> Dict[str, str]:
    """Build a reverse index slug -> tmdb_id (string) from an existing mapping.

    Note: If the existing CSV contains duplicate slugs, the last tmdb_id wins.
    This is only used for fast membership checks during --resume.
    """

    slug_to_tmdb: Dict[str, str] = {}
    for tmdb_id, slug in tmdb_to_slug.items():
        if tmdb_id and slug:
            slug_to_tmdb[slug] = tmdb_id
    return slug_to_tmdb


def _fmt_eta(seconds: float) -> str:
    if seconds < 0 or seconds != seconds:  # NaN
        return "?"
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, s2 = divmod(rem, 60)
    if h:
        return f"{h:d}h{m:02d}m"
    return f"{m:d}m{s2:02d}s"


def _print_progress(
    processed: int,
    total: Optional[int],
    wrote: int,
    misses: int,
    skipped_existing: int,
    start_time: float,
    bar_width: int = 28,
) -> None:
    # Only draw an in-place progress bar when stderr is a TTY.
    if not sys.stderr.isatty():
        return

    elapsed = max(0.001, time.time() - start_time)
    rate = processed / elapsed

    if total and total > 0:
        frac = min(1.0, processed / float(total))
        filled = int(bar_width * frac)
        bar = "#" * filled + "-" * (bar_width - filled)
        remaining = max(0, total - processed)
        eta = _fmt_eta(remaining / max(rate, 1e-9))
        msg = (
            f"[{bar}] {processed}/{total} ({frac*100:5.1f}%) "
            f"wrote={wrote} misses={misses} skipped={skipped_existing} "
            f"{rate:5.2f}/s ETA {eta}"
        )
    else:
        msg = (
            f"processed={processed} wrote={wrote} misses={misses} skipped={skipped_existing} "
            f"{rate:5.2f}/s"
        )

    print("\r" + msg[:200].ljust(200), end="", file=sys.stderr, flush=True)


def _fmt_timestamp(t: float) -> str:
    try:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t))
    except Exception:
        return "?"


def _print_checkpoint(
    *,
    processed: int,
    total: Optional[int],
    wrote: int,
    misses: int,
    skipped_existing: int,
    chunk_n: int,
    chunk_elapsed: float,
    tmdb_calls: int,
    chunk_calls: int,
) -> None:
    rate = chunk_n / max(0.001, chunk_elapsed)
    call_rate = chunk_calls / max(0.001, chunk_elapsed)
    finish_at = "?"
    eta = "?"
    if total and total > 0:
        remaining = max(0, total - processed)
        seconds_left = remaining / max(rate, 1e-9)
        eta = _fmt_eta(seconds_left)
        finish_at = _fmt_timestamp(time.time() + seconds_left)

    print(
        f"[{_fmt_timestamp(time.time())}] checkpoint: processed={processed} wrote={wrote} "
        f"misses={misses} skipped={skipped_existing} last{chunk_n}={rate:5.2f}/s "
        f"tmdb_calls={tmdb_calls} last_calls={chunk_calls} ({call_rate:5.1f}/s) "
        f"ETA {eta} finish {finish_at}",
        file=sys.stderr,
        flush=True,
    )


def _count_data_rows(csv_path: Path) -> int:
    # Counts lines minus header; safe for reasonably sized CSVs.
    with csv_path.open("r", encoding="utf-8", errors="replace") as f:
        n = sum(1 for _ in f)
    return max(0, n - 1)


def _load_state(state_path: Path) -> Dict[str, object]:
    if not state_path.exists():
        return {}
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(state_path: Path, state: Dict[str, object]) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = state_path.with_suffix(state_path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(state_path)


def _load_tmdb_key_from_frontend_env(repo_root: Path) -> str:
    """Best-effort: read VITE_TMDB_V3 from frontend/.env.

    This keeps the CLI command clean (no subshell/grep) while avoiding hard-coding a key in the script.
    """

    env_path = repo_root / "frontend" / ".env"
    if not env_path.exists():
        return ""
    try:
        for raw_line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if not line.startswith("VITE_TMDB_V3="):
                continue
            val = line.split("=", 1)[1].strip().strip('"').strip("'")
            return val
    except Exception:
        return ""
    return ""


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--movie-data", required=True, help="Path to movie_data.csv")
    ap.add_argument(
        "--out",
        default=str(Path(__file__).resolve().parents[1] / "models" / "tmdb_to_slug.csv"),
        help="Output path for tmdb_to_slug.csv",
    )
    ap.add_argument(
        "--review-out",
        default=str(Path(__file__).resolve().parents[1] / "models" / "tmdb_to_slug_review.csv"),
        help="Output path for review CSV (low-confidence, collisions, no-matches)",
    )
    ap.add_argument(
        "--api-key",
        default=os.environ.get("TMDB_API_KEY")
        or os.environ.get("VITE_TMDB_V3")
        or os.environ.get("TMDB_V3")
        or "",
        help="TMDB API key. If omitted, uses TMDB_API_KEY/VITE_TMDB_V3 env vars, then tries frontend/.env (VITE_TMDB_V3).",
    )
    ap.add_argument("--limit", type=int, default=0, help="Max rows to process (0 = no limit)")
    ap.add_argument(
        "--sleep",
        type=float,
        default=0.0,
        help="Extra seconds to sleep after each input row (usually leave at 0; use --max-rps for throttling)",
    )
    ap.add_argument(
        "--max-rps",
        type=float,
        default=45.0,
        help="Max TMDB HTTP requests per second (client-side throttle; 0 disables throttling)",
    )
    ap.add_argument(
        "--workers",
        type=int,
        default=16,
        help="Number of concurrent worker threads for TMDB lookups (higher can be faster; still capped by --max-rps)",
    )
    ap.add_argument(
        "--inflight",
        type=int,
        default=0,
        help="Max number of in-flight TMDB lookup tasks (0 = auto)",
    )
    ap.add_argument(
        "--review-threshold",
        type=float,
        default=0.78,
        help="Matches with score below this (but above the hard acceptance threshold) go to review CSV",
    )
    ap.add_argument(
        "--no-precount",
        action="store_true",
        help="Do not pre-count CSV rows for a percentage/ETA progress bar",
    )
    ap.add_argument(
        "--resume",
        action="store_true",
        help="Resume by skipping tmdb_ids already present in output",
    )
    ap.add_argument(
        "--checkpoint-every",
        type=int,
        default=200,
        help="Print a durable checkpoint line every N processed rows (0 = disable)",
    )
    ap.add_argument(
        "--heartbeat-seconds",
        type=int,
        default=30,
        help="Print a durable heartbeat line every N seconds (0 = disable). Useful when logs are redirected.",
    )
    ap.add_argument(
        "--state",
        default=str(Path(__file__).resolve().parents[1] / "models" / "tmdb_to_slug_state.json"),
        help="Path to a JSON state file for resumable runs (used with --resume)",
    )
    ap.add_argument(
        "--max-seconds",
        type=int,
        default=0,
        help="Hard wall-clock limit for this run in seconds (0 = no limit). When hit, logs and exits non-zero.",
    )

    args = ap.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[2]
    api_key = (args.api_key or "").strip().strip('"').strip("'")
    if not api_key:
        api_key = _load_tmdb_key_from_frontend_env(repo_root)
    if not api_key:
        print(
            "Missing TMDB API key. Provide --api-key, set TMDB_API_KEY, or set VITE_TMDB_V3 in frontend/.env.",
            file=sys.stderr,
            flush=True,
        )
        return 2

    in_path = Path(args.movie_data).expanduser().resolve()
    out_path = Path(args.out).expanduser().resolve()
    review_path = Path(args.review_out).expanduser().resolve()
    state_path = Path(args.state).expanduser().resolve() if args.state else None
    out_path.parent.mkdir(parents=True, exist_ok=True)
    review_path.parent.mkdir(parents=True, exist_ok=True)
    if state_path is not None:
        state_path.parent.mkdir(parents=True, exist_ok=True)

    existing = _load_existing(out_path) if args.resume else {}
    existing_slug_to_tmdb = _build_slug_index(existing) if args.resume else {}
    existing_slugs = set(existing.values())

    limiter = RateLimiter(float(args.max_rps or 0.0))

    workers = max(1, int(args.workers or 1))
    inflight = int(args.inflight or 0)
    if inflight <= 0:
        inflight = max(workers * 8, 64)

    # Best-effort: pick up previous progress counters for logging (we do not skip input rows by offset).
    resume_offset = 0
    if args.resume and state_path is not None:
        st = _load_state(state_path)
        resume_offset = _coerce_int(st.get("processed_rows")) or 0

    processed = 0
    processed_this_run = 0
    wrote = 0
    skipped_existing = 0
    misses = 0
    reviewed = 0
    tmdb_calls = 0

    tmdb_calls_lock = threading.Lock()
    thread_local = threading.local()

    def _get_session() -> requests.Session:
        s = getattr(thread_local, "session", None)
        if s is None:
            s = requests.Session()
            thread_local.session = s
        return s

    def _inc_calls() -> None:
        nonlocal tmdb_calls
        with tmdb_calls_lock:
            tmdb_calls += 1

    total: Optional[int] = None
    if args.limit and args.limit > 0:
        total = int(args.limit)
    elif not args.no_precount:
        try:
            total = _count_data_rows(in_path)
        except Exception:
            total = None

    # Write header if creating new file.
    new_file = not out_path.exists()
    f_out = out_path.open("a", encoding="utf-8", newline="")
    new_review_file = not review_path.exists()
    f_review = review_path.open("a", encoding="utf-8", newline="")

    # Track collisions within a single run.
    seen_tmdb_to_slug: Dict[str, str] = {}

    start_time = time.time()
    print(
        f"[{_fmt_timestamp(start_time)}] start: movie_data={in_path} out={out_path} review_out={review_path} "
        f"state={state_path} resume_offset={resume_offset} existing_rows={len(existing)} existing_mapped_slugs={len(existing_slugs)} "
        f"max_rps={float(args.max_rps or 0.0):.2f} workers={workers} inflight={inflight} "
        f"checkpoint_every={int(args.checkpoint_every or 0)} heartbeat_seconds={int(args.heartbeat_seconds or 0)}",
        file=sys.stderr,
        flush=True,
    )
    last_progress = 0.0
    checkpoint_every = max(0, int(args.checkpoint_every or 0))
    last_checkpoint_time = start_time
    last_checkpoint_processed = 0
    last_checkpoint_calls = 0
    heartbeat_seconds = max(0, int(args.heartbeat_seconds or 0))
    last_heartbeat_time = start_time
    last_heartbeat_processed = 0
    last_heartbeat_calls = 0
    deadline: Optional[float] = None
    if args.max_seconds and int(args.max_seconds) > 0:
        deadline = start_time + float(int(args.max_seconds))
    try:
        writer = csv.DictWriter(f_out, fieldnames=["tmdb_id", "slug"])
        if new_file:
            writer.writeheader()

        review_fields = [
            "reason",
            "tmdb_id",
            "slug",
            "score",
            "movie_title",
            "year_released",
            "tmdb_title",
            "tmdb_year",
            "release_date",
            "popularity",
            "existing_slug",
        ]
        review_writer = csv.DictWriter(f_review, fieldnames=review_fields)
        if new_review_file:
            review_writer.writeheader()

        writes_since_flush = 0

        def _write_state(reason: str) -> None:
            if not (args.resume and state_path is not None):
                return
            _save_state(
                state_path,
                {
                    "processed_rows": processed,
                    "processed_this_run": processed_this_run,
                    "wrote": wrote,
                    "misses": misses,
                    "skipped_existing": skipped_existing,
                    "review_rows": reviewed,
                    "updated_at": _fmt_timestamp(time.time()),
                    "reason": reason,
                },
            )

        def _tick() -> None:
            nonlocal last_progress, last_checkpoint_time, last_checkpoint_processed, last_checkpoint_calls, last_heartbeat_time, last_heartbeat_processed, last_heartbeat_calls

            now = time.time()

            if deadline is not None and now >= deadline:
                print("", file=sys.stderr)
                try:
                    f_out.flush()
                    f_review.flush()
                except Exception:
                    pass
                print(
                    f"[{_fmt_timestamp(now)}] TIME LIMIT HIT: max_seconds={int(args.max_seconds)}; "
                    f"exiting early at processed={processed} wrote={wrote} misses={misses} "
                    f"skipped={skipped_existing} review_rows={reviewed}",
                    file=sys.stderr,
                    flush=True,
                )
                _write_state("time_limit_hit")
                raise TimeoutError("time limit hit")

            if now - last_progress >= 0.25:
                _print_progress(
                    processed=processed,
                    total=total,
                    wrote=wrote,
                    misses=misses,
                    skipped_existing=skipped_existing,
                    start_time=start_time,
                )
                last_progress = now

            if heartbeat_seconds and (now - last_heartbeat_time) >= float(heartbeat_seconds):
                try:
                    f_out.flush()
                    f_review.flush()
                except Exception:
                    pass
                chunk_n = processed - last_heartbeat_processed
                chunk_calls = tmdb_calls - last_heartbeat_calls
                chunk_elapsed = now - last_heartbeat_time
                row_rate = chunk_n / max(0.001, chunk_elapsed)
                call_rate = chunk_calls / max(0.001, chunk_elapsed)
                eta = "?"
                finish_at = "?"
                if total and total > 0:
                    remaining = max(0, total - processed)
                    seconds_left = remaining / max(row_rate, 1e-9)
                    eta = _fmt_eta(seconds_left)
                    finish_at = _fmt_timestamp(time.time() + seconds_left)
                print(
                    f"[{_fmt_timestamp(now)}] heartbeat: processed={processed} wrote={wrote} misses={misses} "
                    f"skipped={skipped_existing} tmdb_calls={tmdb_calls} "
                    f"rate={row_rate:5.2f}/s calls={call_rate:5.1f}/s ETA {eta} finish {finish_at}",
                    file=sys.stderr,
                    flush=True,
                )
                last_heartbeat_time = now
                last_heartbeat_processed = processed
                last_heartbeat_calls = tmdb_calls
                _write_state("heartbeat")

            if (
                checkpoint_every
                and processed
                and processed % checkpoint_every == 0
                and processed != last_checkpoint_processed
            ):
                try:
                    f_out.flush()
                    f_review.flush()
                except Exception:
                    pass
                chunk_n = processed - last_checkpoint_processed
                chunk_calls = tmdb_calls - last_checkpoint_calls
                chunk_elapsed = now - last_checkpoint_time
                # End the in-place progress bar line before printing.
                print("", file=sys.stderr)
                _print_checkpoint(
                    processed=processed,
                    total=total,
                    wrote=wrote,
                    misses=misses,
                    skipped_existing=skipped_existing,
                    chunk_n=chunk_n,
                    chunk_elapsed=chunk_elapsed,
                    tmdb_calls=tmdb_calls,
                    chunk_calls=chunk_calls,
                )
                # Redraw progress bar after the checkpoint.
                _print_progress(
                    processed=processed,
                    total=total,
                    wrote=wrote,
                    misses=misses,
                    skipped_existing=skipped_existing,
                    start_time=start_time,
                )
                last_progress = now
                last_checkpoint_time = now
                last_checkpoint_processed = processed
                last_checkpoint_calls = tmdb_calls
                _write_state("checkpoint")

        def _worker(row: MovieRow) -> Tuple[MovieRow, Optional[Match], Optional[str]]:
            try:
                match = _resolve_tmdb_match(
                    _get_session(),
                    api_key,
                    row.title,
                    row.year,
                    limiter,
                    on_request=_inc_calls,
                )
                if args.sleep and args.sleep > 0:
                    time.sleep(args.sleep)
                return (row, match, None)
            except Exception as e:
                if args.sleep and args.sleep > 0:
                    time.sleep(args.sleep)
                return (row, None, str(e))

        def _handle(row: MovieRow, match: Optional[Match], err: Optional[str]) -> None:
            nonlocal processed, processed_this_run, wrote, skipped_existing, misses, reviewed, writes_since_flush

            processed += 1
            processed_this_run += 1

            # With many workers, duplicate slugs can be in-flight before the first result
            # updates existing_slugs. During --resume, treat slug as the durable unique key
            # and avoid writing any additional mappings for slugs already mapped.
            if args.resume and row.slug in existing_slugs:
                skipped_existing += 1
                _tick()
                return

            if err:
                print(f"TMDB error for {row.title!r} ({row.year}): {err}", file=sys.stderr, flush=True)
                misses += 1
                review_writer.writerow(
                    {
                        "reason": "tmdb_error",
                        "tmdb_id": "",
                        "slug": row.slug,
                        "score": "",
                        "movie_title": row.title,
                        "year_released": row.year or "",
                        "tmdb_title": "",
                        "tmdb_year": "",
                        "release_date": "",
                        "popularity": "",
                        "existing_slug": "",
                    }
                )
                reviewed += 1
                writes_since_flush += 1
                if writes_since_flush >= 200:
                    f_out.flush()
                    f_review.flush()
                    writes_since_flush = 0
                _tick()
                return

            if match is None:
                misses += 1
                review_writer.writerow(
                    {
                        "reason": "no_match",
                        "tmdb_id": "",
                        "slug": row.slug,
                        "score": "",
                        "movie_title": row.title,
                        "year_released": row.year or "",
                        "tmdb_title": "",
                        "tmdb_year": "",
                        "release_date": "",
                        "popularity": "",
                        "existing_slug": "",
                    }
                )
                reviewed += 1
                writes_since_flush += 1
                if writes_since_flush >= 200:
                    f_out.flush()
                    f_review.flush()
                    writes_since_flush = 0
                _tick()
                return

            tmdb_id_s = str(match.tmdb_id)
            if tmdb_id_s in existing:
                skipped_existing += 1
                # If this row maps to a different slug than what's already recorded, flag it.
                if existing[tmdb_id_s] != row.slug:
                    review_writer.writerow(
                        {
                            "reason": "collision_existing",
                            "tmdb_id": match.tmdb_id,
                            "slug": row.slug,
                            "score": f"{match.score:.4f}",
                            "movie_title": row.title,
                            "year_released": row.year or "",
                            "tmdb_title": match.tmdb_title,
                            "tmdb_year": match.tmdb_year or "",
                            "release_date": match.release_date,
                            "popularity": f"{match.popularity:.4f}",
                            "existing_slug": existing[tmdb_id_s],
                        }
                    )
                    reviewed += 1
                    writes_since_flush += 1
                if writes_since_flush >= 200:
                    f_out.flush()
                    f_review.flush()
                    writes_since_flush = 0
                _tick()
                return

            # Collision within this run.
            if tmdb_id_s in seen_tmdb_to_slug and seen_tmdb_to_slug[tmdb_id_s] != row.slug:
                review_writer.writerow(
                    {
                        "reason": "collision_run",
                        "tmdb_id": match.tmdb_id,
                        "slug": row.slug,
                        "score": f"{match.score:.4f}",
                        "movie_title": row.title,
                        "year_released": row.year or "",
                        "tmdb_title": match.tmdb_title,
                        "tmdb_year": match.tmdb_year or "",
                        "release_date": match.release_date,
                        "popularity": f"{match.popularity:.4f}",
                        "existing_slug": seen_tmdb_to_slug[tmdb_id_s],
                    }
                )
                reviewed += 1
                writes_since_flush += 1
                if writes_since_flush >= 200:
                    f_out.flush()
                    f_review.flush()
                    writes_since_flush = 0
                _tick()
                return

            seen_tmdb_to_slug[tmdb_id_s] = row.slug
            existing_slugs.add(row.slug)
            if args.resume:
                existing_slug_to_tmdb[row.slug] = tmdb_id_s

            writer.writerow({"tmdb_id": match.tmdb_id, "slug": row.slug})
            wrote += 1
            existing[tmdb_id_s] = row.slug
            writes_since_flush += 1

            # Low-confidence: keep mapping, but add to review.
            if float(match.score) < float(args.review_threshold):
                review_writer.writerow(
                    {
                        "reason": "low_confidence",
                        "tmdb_id": match.tmdb_id,
                        "slug": row.slug,
                        "score": f"{match.score:.4f}",
                        "movie_title": row.title,
                        "year_released": row.year or "",
                        "tmdb_title": match.tmdb_title,
                        "tmdb_year": match.tmdb_year or "",
                        "release_date": match.release_date,
                        "popularity": f"{match.popularity:.4f}",
                        "existing_slug": "",
                    }
                )
                reviewed += 1
                writes_since_flush += 1

            if writes_since_flush >= 200:
                f_out.flush()
                f_review.flush()
                writes_since_flush = 0

            _tick()

        pending = set()

        with ThreadPoolExecutor(max_workers=workers) as ex:
            for row in _iter_rows(in_path):
                if args.limit and processed_this_run >= args.limit:
                    break

                # If resuming and we've already mapped this slug, skip without hitting TMDB.
                if args.resume and row.slug in existing_slugs:
                    skipped_existing += 1
                    processed += 1
                    processed_this_run += 1
                    _tick()
                    continue

                pending.add(ex.submit(_worker, row))

                # If we have too many in-flight tasks, drain some.
                while pending and (
                    len(pending) >= inflight
                    or (args.limit and (processed_this_run + len(pending)) >= args.limit)
                ):
                    done, pending = wait(pending, return_when=FIRST_COMPLETED)
                    for fut in done:
                        r0, m0, e0 = fut.result()
                        _handle(r0, m0, e0)

            # Drain remaining tasks.
            while pending and (not args.limit or processed_this_run < args.limit):
                done, pending = wait(pending, return_when=FIRST_COMPLETED)
                for fut in done:
                    r0, m0, e0 = fut.result()
                    _handle(r0, m0, e0)

        # Final flush.
        f_out.flush()
        f_review.flush()

    except TimeoutError:
        return 3

    finally:
        f_out.close()
        f_review.close()

    # Final progress line + newline.
    _print_progress(
        processed=processed,
        total=total,
        wrote=wrote,
        misses=misses,
        skipped_existing=skipped_existing,
        start_time=start_time,
    )
    print("", file=sys.stderr)

    print(
        f"done: processed={processed} wrote={wrote} misses={misses} skipped_existing={skipped_existing} review_rows={reviewed} out={out_path} review_out={review_path}",
        file=sys.stderr,
        flush=True,
    )
    if args.resume and state_path is not None:
        _save_state(
            state_path,
            {
                "processed_rows": processed,
                "processed_this_run": processed_this_run,
                "wrote": wrote,
                "misses": misses,
                "skipped_existing": skipped_existing,
                "review_rows": reviewed,
                "updated_at": _fmt_timestamp(time.time()),
                "reason": "completed",
            },
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
