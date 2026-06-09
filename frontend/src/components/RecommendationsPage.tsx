import { useEffect, useRef, useState } from 'react'
import Slider from 'rc-slider'
import 'rc-slider/assets/index.css'

import backgroundVideo from '../../../Resources/trimmed.mp4'
import './RecommendationsPage.css'
import { useAuth } from '../auth/useAuth';
import { Link } from 'react-router-dom';

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

export default function RecommendationsPage() {
  const { isAuthenticated, user, logout, isLoading } = useAuth();
  const [query, setQuery] = useState('')
  const [movies, setMovies] = useState<Movie[]>([])
  const [loading, setLoading] = useState(false)
  const [selectedMovies, setSelectedMovies] = useState<number[]>([])
  const [ratings, setRatings] = useState<Record<number, number>>({})

  const [recsLoading, setRecsLoading] = useState(false)
  const [recsError, setRecsError] = useState<string | null>(null)
  const [loadingDots, setLoadingDots] = useState('')
  const dotsIntervalRef = useRef<number | null>(null)

  const TMDB_V3 = import.meta.env.VITE_TMDB_V3 as string
  const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string) || 'http://localhost:8000'

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
    setSelectedMovies(prev => {
      if (prev.includes(id)) {
        setRatings(r => { const copy = { ...r }; delete copy[id]; return copy })
        return prev.filter(x => x !== id)
      }
      return [...prev, id]
    })
  }

  const handleRatingChange = (id: number, value: number) => {
    setRatings(r => ({ ...r, [id]: value }))
  }

  const getRatingIcon = (rating: number): string => {
    if (rating <= 3) return '🤢'
    if (rating <= 6) return '😃'
    if (rating <= 8) return '❤️'
    return '❤️‍🔥'
  }

  const ratedMovies = selectedMovies
    .map(id => ({ id, rating: ratings[id] }))
    .filter(x => typeof x.rating === 'number' && !Number.isNaN(x.rating))

  const canGetRecs = ratedMovies.length >= 5

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
            <span>Welcome, {user?.username}</span>
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
            <div className="pill">Rated: {ratedMovies.length} / 5</div>
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
              const year = (movie as any).release_date ? ` (${(movie as any).release_date.slice(0,4)})` : ''
              return (
                <li
                  key={movie.id}
                  onClick={() => toggleSelect(movie.id)}
                  className={`searchRow ${isSelected ? 'cardSelected' : ''}`}
                >
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
                            value={ratings[movie.id] ?? 5}
                            onChange={value => handleRatingChange(movie.id, value as number)}
                            className="rating-slider"
                          />
                          <div className="rating-display">
                            <span className="rating-icon">{getRatingIcon(ratings[movie.id] ?? 5)}</span>
                            <span className="rating-value">{ratings[movie.id] ?? 5}</span>
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