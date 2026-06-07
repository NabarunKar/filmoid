import { Route, Routes } from 'react-router-dom'
import RecommendationsPage from './components/RecommendationsPage'
import ResultsPage from './pages/ResultsPage'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<RecommendationsPage />} />
      <Route path="/recommendations" element={<ResultsPage />} />
    </Routes>
  )
}

