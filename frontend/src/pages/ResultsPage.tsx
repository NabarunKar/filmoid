import { useEffect, useState } from 'react'
import { Movie } from '../components/RecommendationsPage'
import './ResultsPage.css'

export default function ResultsPage() {
  const [recommendations, setRecommendations] = useState<Movie[]>([])

  useEffect(() => {
    const recsData = localStorage.getItem('recommendations')
    if (recsData) {
      try {
        const parsedRecs = JSON.parse(recsData) as Movie[]
        setRecommendations(parsedRecs)
        localStorage.removeItem('recommendations')
      } catch (e) {
        console.error('Error parsing recommendations from localStorage', e)
      }
    }
  }, [])

  return (
    <div className="resultsPage">
      <div className="resultsInner">
        <h1>Your Recommendations</h1>
        {recommendations.length > 0 ? (
          <ul className="resultsList">
            {recommendations.map(movie => {
              const year = (movie as any).release_date ? ` (${(movie as any).release_date.slice(0, 4)})` : ''
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
                  <div className="resultTitle">
                    {movie.title}
                    {year}
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
