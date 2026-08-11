import { motion } from 'framer-motion'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { adminAuthApi } from './api/adminApi'
import AlertsModule from './components/AlertsModule'
import Library from './components/Library'
import AdminLayout from './layouts/AdminLayout'
import AppLayout from './layouts/AppLayout'
import AdminDashboard from './pages/AdminDashboard'
import AdminLogs from './pages/AdminLogs'
import AdminRecords from './pages/AdminRecords'
import AdminReports from './pages/AdminReports'
import AdminSettings from './pages/AdminSettings'
import AdminUsers from './pages/AdminUsers'
import Dashboard from './pages/Dashboard'
import DetectionDetails from './pages/DetectionDetails'
import DiseaseDetection from './pages/DiseaseDetection'
import GetStarted from './pages/GetStarted'
import Landing from './pages/Landing'
import Loading from './pages/Loading'
import Login from './pages/Login'
import Signup from './pages/Signup'
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
    
    // Check for admin user (has isAdmin flag and username)
    if (parsed?.isAdmin === true && parsed?.Username) {
      return true
    }
    
    // Check for regular user.
    // Accept users with single-word names (firstName only) and fallback identity fields.
    const firstName = String(parsed?.firstName ?? '').trim()
    const lastName = String(parsed?.lastName ?? '').trim()
    const username = String(parsed?.Username ?? parsed?.username ?? '').trim()
    const email = String(parsed?.Email ?? parsed?.email ?? '').trim()

    return Boolean(firstName || lastName || username || email)
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

function RequireAdmin({ children }) {
  const location = useLocation()

  if (!adminAuthApi.isAuthenticated()) {
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
      <Route path="/signup" element={<Signup />} />
      <Route path="/admin/login" element={<Navigate to="/login" replace />} />

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

      {/* Admin Routes */}
      <Route
        path="/admin"
        element={
          <RequireAdmin>
            <AdminLayout />
          </RequireAdmin>
        }
      >
        <Route index element={<Navigate to="/admin/dashboard" replace />} />
        <Route path="dashboard" element={<AdminDashboard />} />
        <Route path="library" element={<Library />} />
        <Route path="users" element={<AdminUsers />} />
        <Route path="logs" element={<AdminLogs />} />
        <Route path="records" element={<AdminRecords />} />
        <Route path="reports" element={<AdminReports />} />
        <Route path="settings" element={<AdminSettings />} />
        <Route path="*" element={<Navigate to="/admin/dashboard" replace />} />
      </Route>

      <Route path="*" element={<Navigate to="/landing" replace />} />
    </Routes>
  )
}

export default App
