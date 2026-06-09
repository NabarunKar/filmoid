import { Route, Routes } from 'react-router-dom'
import RecommendationsPage from './components/RecommendationsPage'
import ResultsPage from './pages/ResultsPage'
import LoginPage from './pages/LoginPage'
import SignupPage from './pages/SignupPage'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<RecommendationsPage />} />
      <Route path="/recommendations" element={<ResultsPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />
    </Routes>
  )
}

