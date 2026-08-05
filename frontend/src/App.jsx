import { motion } from 'framer-motion'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import AlertsModule from './components/AlertsModule'
import Library from './components/Library'
import AppLayout from './layouts/AppLayout'
import Dashboard from './pages/Dashboard'
import DetectionDetails from './pages/DetectionDetails'
import DiseaseDetection from './pages/DiseaseDetection'
import GetStarted from './pages/GetStarted'
import Landing from './pages/Landing'
import Loading from './pages/Loading'
import Login from './pages/Login'
import Profile from './pages/Profile'
import Report from './pages/Report'
import Reports from './pages/Reports'
import YieldPrediction from './pages/YieldPrediction'

const AppLayoutWithTransition = () => (
  <motion.div
    initial={{ opacity: 0 }}
    animate={{ opacity: 1 }}
    transition={{ duration: 0.4, ease: 'easeOut' }}
  >
    <AppLayout />
  </motion.div>
)

function hasPitayaUser() {
  try {
    const raw = localStorage.getItem('pitayaUser')
    if (!raw) return false
    const parsed = JSON.parse(raw)
    return Boolean(String(parsed?.firstName ?? '').trim()) && Boolean(String(parsed?.lastName ?? '').trim())
  } catch {
    return false
  }
}

function RequireUser({ children }) {
  const location = useLocation()

  if (!hasPitayaUser()) {
    return <Navigate to="/login" replace state={{ from: location }} />
  }

  return children
}

function App() {
  return (
    <Routes>
      <Route path="/" element={<Loading />} />
      <Route path="/landing" element={<Landing />} />
      <Route path="/get-started" element={<GetStarted />} />
      <Route path="/login" element={<Login />} />

      <Route
        path="/app"
        element={
          <RequireUser>
            <AppLayoutWithTransition />
          </RequireUser>
        }
      >
        <Route index element={<Navigate to="/app/dashboard" replace />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="identify" element={<DiseaseDetection />} />
        <Route path="library" element={<Library />} />
        <Route path="alerts" element={<AlertsModule />} />
        <Route path="reports" element={<Reports />} />
        <Route path="yield-report" element={<Reports initialTab="yield" />} />
        <Route path="yield" element={<YieldPrediction />} />
        <Route path="profile" element={<Profile />} />
        <Route path="detection/:id" element={<DetectionDetails />} />
        <Route path="report" element={<Report />} />
        <Route path="*" element={<Navigate to="/app/dashboard" replace />} />
      </Route>
      <Route path="*" element={<Navigate to="/landing" replace />} />
    </Routes>
  )
}

export default App
