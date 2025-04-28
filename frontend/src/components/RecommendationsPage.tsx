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

  // load your TMDb v3 key from .env
  const TMDB_V3 = import.meta.env.VITE_TMDB_V3 as string

  // fetch TMDb whenever query changes
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

  // toggle selection, max 5
  const toggleSelect = (id: number) => {
    setSelectedMovies(prev => {
      if (prev.includes(id)) {
        return prev.filter(x => x !== id)
      }
      if (prev.length >= 5) {
        alert('You can only select up to 5 movies')
        return prev
      }
      return [...prev, id]
    })
  }

  // for debugging / later use
  useEffect(() => {
    console.log('Selected movie IDs:', selectedMovies)
  }, [selectedMovies])

  return (
    <div className="relative w-full min-h-screen bg-[#181C14] text-[#ECDFCC]">
      {/* absolutely-centered search box */}
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

      {/* results below, with a little top-padding */}
      <div className="pt-[60vh] px-8">
        <p className="text-center mb-4">
          Selected {selectedMovies.length} / 5
        </p>
        <ul className="space-y-4">
          {movies.map(movie => (
            <li
            key={movie.id}
            onClick={() => toggleSelect(movie.id)}
            className={`
              flex
              flex-col              /* stack image above title */
              items-center          /* center everything horizontally */
              gap-2
              p-2
              rounded-md
              cursor-pointer
              ${selectedMovies.includes(movie.id) ? 'ring-4 ring-[#ECDFCC]' : ''}
            `}
          >
            {movie.poster_path ? (
              <img
                src={`https://image.tmdb.org/t/p/w1280${movie.poster_path}`}
                alt={movie.title}
                className="w-1/4 h-auto rounded"  /* 25% width, auto height */
              />
            ) : (
              <div className="h-6 w-4 bg-gray-700 flex items-center justify-center">
                N/A
              </div>
            )}
            <span className="text-lg text-center">{movie.title}</span>
          </li>
          
          ))}
        </ul>
      </div>
    </div>
  )
}