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

  // read your TMDB token from Vite’s env
  const TMDB_V3 = import.meta.env.VITE_TMDB_V3 as string

  // fetch whenever query changes (you can add debounce later)
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
  
        // Add your v3 key here:
        url.searchParams.set('api_key', TMDB_V3)
  
        console.log('Fetching:', url.toString())
  
        const res = await fetch(url.toString(), {
          headers: { accept: 'application/json' },
          signal: controller.signal
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

  return (
    <div className="min-h-screen bg-[#181C14] text-[#ECDFCC] p-8">
      <h2 className="text-2xl mb-4">Search for a movie</h2>

      <input
        type="text"
        placeholder="Type a movie name..."
        value={query}
        onChange={e => setQuery(e.target.value)}
        className="w-full max-w-md p-2 rounded bg-[#3C3D37] focus:outline-none focus:ring focus:ring-[#ECDFCC]"
      />

      {loading && <p className="mt-4">Loading…</p>}

      <ul className="mt-6 space-y-4">
        {movies.map(movie => (
          <li key={movie.id} className="flex items-center gap-4">
            {movie.poster_path ? (
              <img
                src={`https://image.tmdb.org/t/p/w1280${movie.poster_path}`}
                alt={movie.title}
                className="h-24 rounded"
              />
            ) : (
              <div className="h-24 w-16 bg-gray-700 flex items-center justify-center">N/A</div>
            )}
            <span className="text-lg">{movie.title}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}