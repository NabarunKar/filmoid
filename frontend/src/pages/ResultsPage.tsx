import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Movie } from '../components/RecommendationsPage'
import './ResultsPage.css'

export default function ResultsPage() {
  const [recommendations, setRecommendations] = useState<Movie[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchParams] = useSearchParams()

  const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string) || 'http://localhost:8000'

  useEffect(() => {
    const sessionId = searchParams.get('id')
    if (!sessionId) {
      setError('No recommendation session ID found in the URL.')
      setLoading(false)
      return
    }

    const fetchRecommendations = async () => {
      setLoading(true)
      setError(null)
      try {
        const res = await fetch(`${API_BASE_URL}/api/recommendations/${sessionId}`)
        if (!res.ok) {
          let message = `Request failed (${res.status})`
          if (res.status === 404) {
            message = 'This recommendation session has expired or is invalid.'
          } else {
            try {
              const json = await res.json()
              if (json?.detail) message = String(json.detail)
            } catch {
              // ignore
            }
          }
          throw new Error(message)
        }
        const data = await res.json()
        setRecommendations(data.recommendations || [])
      } catch (e) {
        setError((e as Error).message)
      } finally {
        setLoading(false)
      }
    }

    fetchRecommendations()
  }, [searchParams, API_BASE_URL])

  return (
    <div className="resultsPage">
      <div className="resultsInner">
        <h1>Your Recommendations</h1>
        {loading ? (
          <p>Loading recommendations...</p>
        ) : error ? (
          <p className="errorText">{error}</p>
        ) : recommendations.length > 0 ? (
          <ul className="resultsList">
            {recommendations.map(movie => {
              const year = movie.release_date ? ` (${movie.release_date.slice(0, 4)})` : ''
              return (
                <li key={movie.id} className="resultRow">
                  {movie.poster_path ? (
                    <img
                      className="resultPoster"
                      src={`https://image.tmdb.org/t/p/w154${movie.poster_path}`}
                      alt={movie.title}
                    />
                  ) : (
                    <div className="resultPoster posterFallback">No poster</div>
                  )}
                  <div className="resultDetails">
                    <div className="resultTitle">
                      {movie.title}
                      {year}
                    </div>
                    {typeof movie.score === 'number' && (
                      <div className="resultScore">
                        Predicted Rating: {Math.min(10, movie.score).toFixed(1)} / 10
                      </div>
                    )}
                  </div>
                </li>
              )
            })}
          </ul>
        ) : (
          <p>No recommendations found in this session.</p>
        )}
      </div>
    </div>
  )
}
