import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import './ResultsPage.css'
import { Trash2 } from 'lucide-react'

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

export default function RatingsPage() {
  const { isAuthenticated, isLoading } = useAuth()
  const navigate = useNavigate()

  const [ratings, setRatings] = useState<UserRating[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string) || 'http://localhost:8000'

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      navigate('/login')
    }
  }, [isLoading, isAuthenticated, navigate])

  useEffect(() => {
    const load = async () => {
      if (!isAuthenticated) {
        setLoading(false)
        return
      }

      setLoading(true)
      setError(null)
      try {
        const res = await fetch(`${API_BASE_URL}/api/users/me/ratings`, {
          credentials: 'include',
          headers: { 'content-type': 'application/json' },
        })
        if (!res.ok) {
          let message = `Request failed (${res.status})`
          try {
            const json = await res.json()
            if (json?.detail) message = String(json.detail)
          } catch {
            // ignore
          }
          throw new Error(message)
        }
        const data = await res.json()
        setRatings(data?.ratings || [])
      } catch (e) {
        setError((e as Error).message)
      } finally {
        setLoading(false)
      }
    }

    load()
  }, [API_BASE_URL, isAuthenticated])

  const deleteRating = async (tmdbId: number, title: string) => {
    const ok = window.confirm(`Remove your rating for ${title}?`)
    if (!ok) return

    setError(null)
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

      setRatings(prev => prev.filter(r => r.tmdb_id !== tmdbId))
    } catch (e) {
      setError((e as Error).message)
    }
  }

  return (
    <div className="resultsPage">
      <div className="resultsInner">
        <h1>Your Ratings</h1>
        {loading ? (
          <p>Loading ratings...</p>
        ) : error ? (
          <p className="errorText">{error}</p>
        ) : ratings.length > 0 ? (
          <ul className="resultsList">
            {ratings.map(r => {
              const year = r.release_date ? ` (${r.release_date.slice(0, 4)})` : ''
              return (
                <li
                  key={r.tmdb_id}
                  className="resultRow"
                  onClick={() => {
                    if (r.tmdb_id) {
                      const letterboxdUrl = `https://letterboxd.com/tmdb/${r.tmdb_id}`
                      window.open(letterboxdUrl, '_blank', 'noopener,noreferrer')
                    }
                  }}
                >
                  <button
                    type="button"
                    className="resultDeleteButton"
                    title="Delete saved rating"
                    onClick={e => {
                      e.stopPropagation()
                      void deleteRating(r.tmdb_id, r.movie_title)
                    }}
                  >
                    <Trash2 size={18} />
                  </button>
                  {r.poster_path ? (
                    <img
                      className="resultPoster"
                      src={`https://image.tmdb.org/t/p/w154${r.poster_path}`}
                      alt={r.movie_title}
                    />
                  ) : (
                    <div className="resultPoster posterFallback">No poster</div>
                  )}
                  <div className="resultDetails">
                    <div className="resultTitle">
                      {r.movie_title}
                      {year}
                    </div>
                    <div className="resultScore">Your Rating: {r.rating.toFixed(1)} / 10</div>
                  </div>
                </li>
              )
            })}
          </ul>
        ) : (
          <p>You haven’t rated any movies yet.</p>
        )}
      </div>
    </div>
  )
}
