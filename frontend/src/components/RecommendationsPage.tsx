import { useEffect, useRef, useState } from 'react'
import Slider from 'rc-slider'
import 'rc-slider/assets/index.css'

import backgroundVideo from '../../../Resources/trimmed.mp4'
import './RecommendationsPage.css'
import { useAuth } from '../auth/useAuth';
import { Link } from 'react-router-dom';
import { Trash2 } from 'lucide-react'

export type Movie = {
  id: number
  title: string
  poster_path: string | null
  release_date?: string
  score?: number
}

type RecommendationResponse = {
  sessionId: string
  recommendations: Movie[]
}

type UserRating = {
  id: string
  user_id: string
  tmdb_id: number
  movie_title: string
  poster_path: string | null
  release_date: string | null
  rating: number
  created_at: string
  updated_at: string
}

export default function RecommendationsPage() {
  const { isAuthenticated, user, logout, isLoading } = useAuth();
  const [query, setQuery] = useState('')
  const [movies, setMovies] = useState<Movie[]>([])
  const [loading, setLoading] = useState(false)
  const [selectedMovies, setSelectedMovies] = useState<number[]>([])
  const [ratings, setRatings] = useState<Record<number, number>>({})
  const [persistedRatings, setPersistedRatings] = useState<UserRating[]>([])

  const [recsLoading, setRecsLoading] = useState(false)
  const [recsError, setRecsError] = useState<string | null>(null)
  const [loadingDots, setLoadingDots] = useState('')
  const dotsIntervalRef = useRef<number | null>(null)

  // Debounced persistence (per-movie) to avoid spamming the backend while dragging.
  const persistTimersRef = useRef<Record<number, number>>({})

  const TMDB_V3 = import.meta.env.VITE_TMDB_V3 as string
  const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string) || 'http://localhost:8000'

  const clearUserRatingState = () => {
    setPersistedRatings([])
    setSelectedMovies([])
    setRatings({})
  }

  // On logout, immediately clear any user-specific rating state to avoid stale UI.
  useEffect(() => {
    if (!isAuthenticated) clearUserRatingState()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAuthenticated])

  // Load latest persisted ratings after login so they count immediately toward rec generation.
  useEffect(() => {
    const loadRatings = async () => {
      if (!isAuthenticated) {
        clearUserRatingState()
        return
      }
      try {
        const res = await fetch(`${API_BASE_URL}/api/users/me/ratings`, {
          credentials: 'include',
          headers: { 'content-type': 'application/json' },
        })
        if (!res.ok) {
          clearUserRatingState()
          return
        }
        const data = await res.json()
        const rows: UserRating[] = data?.ratings || []
        setPersistedRatings(rows)

        // Populate state used by existing recommendation workflow.
        setSelectedMovies(rows.map(r => r.tmdb_id))
        setRatings(Object.fromEntries(rows.map(r => [r.tmdb_id, r.rating])))
      } catch {
        clearUserRatingState()
      }
    }

    loadRatings()
  }, [isAuthenticated, API_BASE_URL])

  useEffect(() => {
    if (!query.trim()) {
      setMovies([])
      return
    }
    if (!TMDB_V3) {
      setMovies([])
      return
    }

    // Debounce search so we don't hit TMDB on every keystroke.
    const controller = new AbortController()
    const handle = window.setTimeout(() => {
      const fetchMovies = async () => {
        setLoading(true)
        try {
          const url = new URL('https://api.themoviedb.org/3/search/movie')
          url.searchParams.set('query', query)
          url.searchParams.set('include_adult', 'false')
          url.searchParams.set('language', 'en-US')
          url.searchParams.set('page', '1')
          url.searchParams.set('api_key', TMDB_V3)

          const res = await fetch(url.toString(), {
            headers: { accept: 'application/json' },
            signal: controller.signal,
          })
          const data = await res.json()
          setMovies(data.results || [])
        } catch (err) {
          if ((err as any).name !== 'AbortError') console.error(err)
        } finally {
          setLoading(false)
        }
      }

      fetchMovies()
    }, 350)

    return () => {
      window.clearTimeout(handle)
      controller.abort()
    }
  }, [query, TMDB_V3])

  const toggleSelect = (id: number) => {
    // Selection is separate from persistence.
    // If a movie already has a persisted rating, clicking the tile should NOT "unrate" it.
    setSelectedMovies(prev => {
      const isPersisted = persistedRatings.some(r => r.tmdb_id === id)
      if (isPersisted) return prev

      if (prev.includes(id)) {
        setRatings(r => {
          const copy = { ...r }
          delete copy[id]
          return copy
        })
        return prev.filter(x => x !== id)
      }
      return [...prev, id]
    })
  }

  const handleRatingChange = (id: number, value: number) => {
    setRatings(r => ({ ...r, [id]: value }))
  }

  const persistRatingIfAuthed = async (movie: Movie, value: number) => {
    if (!isAuthenticated) return
    try {
      const res = await fetch(`${API_BASE_URL}/api/users/me/ratings`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          tmdb_id: movie.id,
          movie_title: movie.title,
          poster_path: movie.poster_path,
          release_date: movie.release_date || null,
          rating: value,
        }),
      })
      if (!res.ok) return

      // Keep the sidebar list fresh and newest-first (updated_at desc)
      const saved = (await res.json()) as UserRating
      setPersistedRatings(prev => {
        const filtered = prev.filter(r => r.tmdb_id !== saved.tmdb_id)
        return [saved, ...filtered].slice(0, 20)
      })
    } catch {
      // ignore
    }
  }

  const deletePersistedRating = async (tmdbId: number, title: string) => {
    if (!isAuthenticated) return

    const ok = window.confirm(`Remove your rating for ${title}?`)
    if (!ok) return

    try {
      const res = await fetch(`${API_BASE_URL}/api/users/me/ratings/${tmdbId}`, {
        method: 'DELETE',
        credentials: 'include',
      })
      if (!res.ok) {
        let message = `Delete failed (${res.status})`
        try {
          const json = await res.json()
          if (json?.detail) message = String(json.detail)
        } catch {
          // ignore
        }
        throw new Error(message)
      }

      // Immediately reflect deletion everywhere in local state.
      setPersistedRatings(prev => prev.filter(r => r.tmdb_id !== tmdbId))
      setSelectedMovies(prev => prev.filter(id => id !== tmdbId))
      setRatings(prev => {
        const copy = { ...prev }
        delete copy[tmdbId]
        return copy
      })
    } catch (e) {
      // Keep it simple for now; future: toast.
      setRecsError((e as Error).message)
    }
  }

  const schedulePersistRatingIfAuthed = (movie: Movie, value: number) => {
    if (!isAuthenticated) return

    const existing = persistTimersRef.current[movie.id]
    if (existing) window.clearTimeout(existing)

    persistTimersRef.current[movie.id] = window.setTimeout(() => {
      void persistRatingIfAuthed(movie, value)
      delete persistTimersRef.current[movie.id]
    }, 500)
  }

  // Cleanup any pending timers on unmount.
  useEffect(() => {
    return () => {
      const timers = persistTimersRef.current
      Object.values(timers).forEach(t => window.clearTimeout(t))
      persistTimersRef.current = {}
    }
  }, [])

  const getRatingIcon = (rating: number): string => {
    if (rating <= 3) return '🤢'
    if (rating <= 6) return '😃'
    if (rating <= 8) return '❤️'
    return '❤️‍🔥'
  }

  const ratedMovies = selectedMovies
    .map(id => ({ id, rating: ratings[id] }))
    .filter(x => typeof x.rating === 'number' && !Number.isNaN(x.rating))

  // Logged-in users: show count from persisted ratings (what they actually have saved).
  // Logged-out users: show count from local in-session ratings.
  const myRatingsCount = isAuthenticated ? persistedRatings.length : ratedMovies.length

  const canGetRecs = ratedMovies.length >= 5

  const openRatingsTab = () => {
    const tab = window.open('about:blank', '_blank')
    if (tab) tab.location.href = '/ratings'
  }

  const getRecommendations = async () => {
    setRecsError(null)

    if (!TMDB_V3) {
      setRecsError('Missing TMDB API key (VITE_TMDB_V3).')
      return
    }

    if (!canGetRecs) {
      setRecsError('Please rate at least 5 movies first.')
      return
    }

    setRecsLoading(true)

    const dotsSequence = ['', '.', '..', '...']
    let dotIndex = 0
    dotsIntervalRef.current = window.setInterval(() => {
      setLoadingDots(dotsSequence[dotIndex])
      dotIndex = (dotIndex + 1) % dotsSequence.length
    }, 400)

    try {
      const res = await fetch(`${API_BASE_URL}/api/recommendations`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          tmdbApiKey: TMDB_V3,
          ratings: ratedMovies.map(x => ({ tmdbId: x.id, rating: x.rating })),
          topN: 10,
        }),
      })

      if (!res.ok) {
        let message = `Request failed (${res.status})`
        const contentType = res.headers.get('content-type') || ''
        try {
          if (contentType.includes('application/json')) {
            const json = await res.json()
            if (json?.detail) message = String(json.detail)
            else message = JSON.stringify(json)
          } else {
            const text = await res.text()
            if (text.trim()) message = text
          }
        } catch {
          // ignore parse errors
        }
        throw new Error(message)
      }

      const data = (await res.json()) as RecommendationResponse
      const recs = data.recommendations || []

      if (recs.length === 0) {
        setRecsError('No recommendations were returned for those movies. Try rating different movies.')
        return
      }

      const resultsTab = window.open('about:blank', '_blank')
      if (resultsTab) {
        resultsTab.location.href = `/recommendations?id=${data.sessionId}`
      } else {
        setRecsError('Could not open a new tab. Please disable your pop-up blocker.')
      }
    } catch (err) {
      setRecsError((err as Error).message)
    } finally {
      if (dotsIntervalRef.current) {
        clearInterval(dotsIntervalRef.current)
        dotsIntervalRef.current = null
      }
      setRecsLoading(false)
    }
  }

  return (
    <div className="recsPage">
      <div className="auth-controls">
        {isLoading ? (
          <p>Loading...</p>
        ) : isAuthenticated ? (
          <>
            <span>Welcome, {user?.username || user?.email}</span>
            <span className="auth-separator">|</span>
            <button onClick={logout} className="auth-button-link">Logout</button>
          </>
        ) : (
          <>
            <Link to="/login">Login</Link>
            <span className="auth-separator">|</span>
            <Link to="/signup">Signup</Link>
          </>
        )}
      </div>
      <video
        className="recsBgVideo recsBgVideoActive"
        autoPlay
        playsInline
        muted
        loop
        preload="auto"
        aria-hidden="true"
        tabIndex={-1}
        disablePictureInPicture
      >
        <source src={backgroundVideo} type="video/mp4" />
      </video>

      <div className="recsOverlay" aria-hidden="true" />
      <div className="recsInner">
        <div className="hero" aria-label="Homepage hero">
          <div className="heroCopy">
            <h1 className="title">Filmoid</h1>
            <p className="subtitle">Let's see what we have got, rate at least 5 movies.</p>
          </div>
          <div className="stats" aria-label="Selection summary">
            <button
              type="button"
              className="pill"
              onClick={openRatingsTab}
              title={
                isAuthenticated
                  ? 'Open your saved ratings'
                  : 'Open your in-session ratings (not saved)'
              }
              style={{ cursor: 'pointer' }}
            >
              My Ratings ({myRatingsCount})
            </button>
          </div>
        </div>

        <div className="panel">
          <div className="controls">
            <input
              className="textInput"
              type="text"
              placeholder="Type a movie name…"
              value={query}
              onChange={e => setQuery(e.target.value)}
            />

            {canGetRecs ? (
              <button
                className="primaryButton"
                type="button"
                disabled={recsLoading}
                onClick={getRecommendations}
              >
                {recsLoading && <div className="spinner" />}
                {recsLoading ? `Preparing your recs${loadingDots}` : "I'm ready for my recs"}
              </button>
            ) : null}
          </div>

          <div className="inlineNote">
            Search for movies, click to select, then rate them 1–10.
          </div>

          {recsError && (
            <div className="errorBox" role="alert">
              <strong>Error:</strong> {recsError}
            </div>
          )}

          {loading && <div className="inlineNote">Loading search results…</div>}

          {/* <h2 className="sectionTitle">Search results</h2> */}
          <ul className="searchResultsList" aria-label="Search results">
            {movies.map(movie => {
              const isSelected = selectedMovies.includes(movie.id)
              const persisted = persistedRatings.find(r => r.tmdb_id === movie.id)
              const hasPersistedRating = Boolean(persisted)
              const year = (movie as any).release_date ? ` (${(movie as any).release_date.slice(0,4)})` : ''
              const sliderValue = (ratings[movie.id] ?? persisted?.rating ?? 5) as number
              return (
                <li
                  key={movie.id}
                  onClick={() => toggleSelect(movie.id)}
                  className={`searchRow ${isSelected ? 'cardSelected' : ''}`}
                >
                  {hasPersistedRating && (
                    <button
                      type="button"
                      className="deleteRatingButton"
                      title="Delete saved rating"
                      onClick={e => {
                        e.stopPropagation()
                        void deletePersistedRating(movie.id, movie.title)
                      }}
                    >
                      <Trash2 size={16} />
                    </button>
                  )}
                  {movie.poster_path ? (
                    <img
                      className="searchPosterSmall"
                      src={`https://image.tmdb.org/t/p/w92${movie.poster_path}`}
                      alt={movie.title}
                    />
                  ) : (
                    <div className="searchPosterSmall posterFallback">No poster</div>
                  )}

                  <div className="movieMeta">
                    <div className="movieTitle">{movie.title}{year}</div>
                    {isSelected && (
                      <div style={{ marginTop: 8 }}>
                        <div className="slider-container" onClick={e => e.stopPropagation()}>
                          <Slider
                            min={0}
                            max={10}
                            step={1}
                            value={sliderValue}
                            onChange={value => {
                              const v = value as number
                              handleRatingChange(movie.id, v)
                              schedulePersistRatingIfAuthed(movie, v)
                            }}
                            className="rating-slider"
                          />
                          <div className="rating-display">
                            <span className="rating-icon">{getRatingIcon(sliderValue)}</span>
                            <span className="rating-value">{sliderValue}</span>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                </li>
              )
            })}
          </ul>
        </div>
      </div>
    </div>
  )
}