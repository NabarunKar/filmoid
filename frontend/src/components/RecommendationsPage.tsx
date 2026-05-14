import React, { useState, useEffect } from 'react'

type Movie = {
  id: number
  title: string
  poster_path: string | null
}

type RecommendationResponse = {
  recommendations: Movie[]
}

export default function RecommendationsPage() {
  const [query, setQuery] = useState('')
  const [movies, setMovies] = useState<Movie[]>([])
  const [loading, setLoading] = useState(false)
  const [selectedMovies, setSelectedMovies] = useState<number[]>([])
  const [ratings, setRatings] = useState<Record<number, number>>({})

  const [recsLoading, setRecsLoading] = useState(false)
  const [recsError, setRecsError] = useState<string | null>(null)
  const [recommendations, setRecommendations] = useState<Movie[]>([])

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

  useEffect(() => {
    console.log('Selected IDs:', selectedMovies)
    console.log('Ratings map:', ratings)
  }, [selectedMovies, ratings])

  const ratedMovies = selectedMovies
    .map(id => ({ id, rating: ratings[id] }))
    .filter(x => typeof x.rating === 'number' && !Number.isNaN(x.rating))

  const canGetRecs = ratedMovies.length >= 5

  const getRecommendations = async () => {
    setRecsError(null)
    setRecommendations([])

    if (!TMDB_V3) {
      setRecsError('Missing TMDB API key (VITE_TMDB_V3).')
      return
    }

    if (!canGetRecs) {
      setRecsError('Please rate at least 5 movies first.')
      return
    }

    setRecsLoading(true)
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
      setRecommendations(recs)

      if (recs.length === 0) {
        setRecsError('No recommendations were returned for those movies. Try rating different movies.')
      }
    } catch (err) {
      setRecsError((err as Error).message)
    } finally {
      setRecsLoading(false)
    }
  }

  return (
    <div
      style={{
        width: '100%',
        minHeight: '100vh',
        background: '#181C14',
        color: '#ECDFCC',
        padding: '2rem',
        boxSizing: 'border-box',
      }}
    >
      <div style={{ maxWidth: 900, margin: '0 auto' }}>
        <h2 style={{ marginTop: 0 }}>Rate movies (min 5)</h2>
        <p style={{ opacity: 0.9, marginTop: 0 }}>
          Search for movies, click to select, then rate them 1–10.
        </p>

        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', flexWrap: 'wrap' }}>
          <input
            type="text"
            placeholder="Type a movie name…"
            value={query}
            onChange={e => setQuery(e.target.value)}
            style={{
              flex: '1 1 320px',
              maxWidth: 520,
              padding: '0.6rem 0.75rem',
              borderRadius: 8,
              border: '1px solid #3C3D37',
              background: '#3C3D37',
              color: '#ECDFCC',
              outline: 'none',
            }}
          />

          <button
            type="button"
            disabled={!canGetRecs || recsLoading}
            onClick={getRecommendations}
            style={{
              padding: '0.6rem 0.9rem',
              borderRadius: 8,
              border: '1px solid transparent',
              background: canGetRecs ? '#ECDFCC' : '#3C3D37',
              color: canGetRecs ? '#181C14' : '#ECDFCC',
              cursor: canGetRecs ? 'pointer' : 'not-allowed',
            }}
          >
            {recsLoading ? 'Getting recs…' : "I'm ready for my recs"}
          </button>
        </div>

        {recsError && (
          <div
            style={{
              marginTop: '0.75rem',
              padding: '0.75rem',
              borderRadius: 8,
              background: '#2b2f25',
              border: '1px solid #3C3D37',
            }}
          >
            <strong>Error:</strong> {recsError}
          </div>
        )}

        {recommendations.length > 0 && (
          <div style={{ marginTop: '1.5rem' }}>
            <h3 style={{ marginBottom: '0.75rem' }}>Your recommendations</h3>
            <ul
              style={{
                listStyle: 'none',
                padding: 0,
                margin: 0,
                display: 'flex',
                flexWrap: 'wrap',
                gap: '1rem',
              }}
            >
              {recommendations.map(movie => (
                <li
                  key={movie.id}
                  style={{
                    width: 180,
                    padding: '0.75rem',
                    borderRadius: 10,
                    background: '#1f241a',
                    boxSizing: 'border-box',
                  }}
                >
                  {movie.poster_path ? (
                    <img
                      src={`https://image.tmdb.org/t/p/w342${movie.poster_path}`}
                      alt={movie.title}
                      style={{ width: '100%', borderRadius: 8, display: 'block' }}
                    />
                  ) : (
                    <div
                      style={{
                        height: 240,
                        borderRadius: 8,
                        background: '#3C3D37',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}
                    >
                      No poster
                    </div>
                  )}
                  <div style={{ marginTop: '0.5rem', fontWeight: 600 }}>{movie.title}</div>
                </li>
              ))}
            </ul>
          </div>
        )}

        <div style={{ marginTop: '0.75rem', opacity: 0.9 }}>
          <div>Selected: {selectedMovies.length}</div>
          <div>Rated: {ratedMovies.length} / 5</div>
        </div>

        {loading && <p style={{ marginTop: '1rem' }}>Loading search results…</p>}

        <ul
          style={{
            listStyle: 'none',
            padding: 0,
            margin: '1.25rem 0 0',
            display: 'flex',
            flexWrap: 'wrap',
            gap: '1rem',
            justifyContent: 'flex-start',
          }}
        >
          {movies.map(movie => {
            const isSelected = selectedMovies.includes(movie.id)
            return (
              <li
                key={movie.id}
                onClick={() => toggleSelect(movie.id)}
                style={{
                  width: 180,
                  padding: '0.75rem',
                  borderRadius: 10,
                  background: '#1f241a',
                  border: isSelected ? '2px solid #ECDFCC' : '2px solid transparent',
                  cursor: 'pointer',
                  boxSizing: 'border-box',
                }}
              >
                {movie.poster_path ? (
                  <img
                    src={`https://image.tmdb.org/t/p/w342${movie.poster_path}`}
                    alt={movie.title}
                    style={{ width: '100%', borderRadius: 8, display: 'block' }}
                  />
                ) : (
                  <div
                    style={{
                      height: 240,
                      borderRadius: 8,
                      background: '#3C3D37',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    No poster
                  </div>
                )}

                <div style={{ marginTop: '0.5rem', fontWeight: 600 }}>{movie.title}</div>

                {isSelected && (
                  <div style={{ marginTop: '0.5rem' }}>
                    <select
                      onClick={e => e.stopPropagation()}
                      value={ratings[movie.id] ?? ''}
                      onChange={e => handleRatingChange(movie.id, Number(e.target.value))}
                      style={{
                        width: '100%',
                        padding: '0.4rem',
                        background: '#3C3D37',
                        color: '#ECDFCC',
                        borderRadius: 8,
                        border: '1px solid #3C3D37',
                      }}
                    >
                      <option value="" disabled>
                        Rate 1–10
                      </option>
                      {Array.from({ length: 10 }, (_, i) => i + 1).map(num => (
                        <option key={num} value={num}>
                          {num}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
              </li>
            )
          })}
        </ul>

        <div style={{ marginTop: '2rem', opacity: 0.9 }}>
          <a href="/home" style={{ color: '#ECDFCC' }}>
            Other tools (mood / Q&A)
          </a>
        </div>
      </div>
    </div>
  )
}