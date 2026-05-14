import React from 'react'
import { Routes, Route } from 'react-router-dom'
import HomePage from './components/Homepage'
import RecommendationsPage from './components/RecommendationsPage'
import MoodPage from './components/MoodPage'
import MovieQuestionPage from './components/MovieQuestionPage'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<RecommendationsPage />} />
      <Route path="/home" element={<HomePage />} />
      <Route path="/recommendations" element={<RecommendationsPage />} />
      <Route path="/mood" element={<MoodPage />} />
      <Route path="/questions" element={<MovieQuestionPage />} />
    </Routes>
  )
}

