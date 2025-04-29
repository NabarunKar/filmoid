import React, { useState, useEffect } from 'react'

type Movie = {
  id: number
  title: string
  poster_path: string | null
}

export default function RecommendationsPage() {
  const [query, setQuery] = useState('')
  const [movies, setMovies] = useState<Movie[]>([])
  const [loading, setLoading] = useState(false)
  const [selectedMovies, setSelectedMovies] = useState<number[]>([])
  const [ratings, setRatings] = useState<Record<number, number>>({})

  const TMDB_V3 = import.meta.env.VITE_TMDB_V3 as string

  useEffect(() => {
    if (!query.trim()) {
      setMovies([])
      return
    }
    const controller = new AbortController()
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
    return () => { controller.abort() }
  }, [query, TMDB_V3])

  const toggleSelect = (id: number) => {
    setSelectedMovies(prev => {
      if (prev.includes(id)) {
        setRatings(r => { const copy = { ...r }; delete copy[id]; return copy })
        return prev.filter(x => x !== id)
      }
      if (prev.length >= 5) {
        alert('You can only select up to 5 movies')
        return prev
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

  return (
    <div className="relative w-full min-h-screen bg-[#181C14] text-[#ECDFCC]">
      {/* Centered search box */}
      <div className="absolute inset-0 flex flex-col items-center justify-center px-8">
        <h2 className="text-2xl mb-4">Search for a movie</h2>
        <input
          type="text"
          placeholder="Type a movie name..."
          value={query}
          onChange={e => setQuery(e.target.value)}
          className="w-full max-w-md p-2 rounded bg-[#3C3D37] focus:outline-none focus:ring focus:ring-[#ECDFCC]"
        />
        {loading && <p className="mt-4">Loading…</p>}
      </div>

      {/* Results & selection/rating */}
      <div className="pt-[60vh] px-8">
        <p className="text-center mb-4">
          Selected {selectedMovies.length} / 5
        </p>
        <ul className="flex flex-wrap justify-center gap-6">
          {movies.map(movie => (
            <li
              key={movie.id}
              onClick={() => toggleSelect(movie.id)}
              className={`
                flex flex-col items-center gap-2 p-2 rounded-md cursor-pointer
                ${selectedMovies.includes(movie.id) ? 'ring-4 ring-[#ECDFCC]' : ''}
              `}
            >
              {/* poster */}
              {movie.poster_path ? (
                <img
                  src={`https://image.tmdb.org/t/p/w1280${movie.poster_path}`}
                  alt={movie.title}
                  className="w-1/4 h-auto rounded"
                />
              ) : (
                <div className="h-24 w-16 bg-gray-700 flex items-center justify-center">
                  N/A
                </div>
              )}

              {/* title */}
              <span className="text-lg text-center">{movie.title}</span>

              {/* rating dropdown, only for selected */}
              {selectedMovies.includes(movie.id) && (
                <select
                  onClick={e => e.stopPropagation()}
                  value={ratings[movie.id] ?? ''}
                  onChange={e => handleRatingChange(movie.id, Number(e.target.value))}
                  className="mt-1 w-20 p-1 bg-[#3C3D37] text-[#ECDFCC] rounded"
                >
                  <option value="" disabled>Rate 1–10</option>
                  {Array.from({ length: 10 }, (_, i) => i + 1).map(num => (
                    <option key={num} value={num}>{num}</option>
                  ))}
                </select>
              )}
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}