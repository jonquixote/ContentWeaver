import { BrowserRouter as Router, Routes, Route, Navigate, useLocation, useNavigate } from 'react-router-dom'
import Dashboard from './components/Dashboard'
import ProjectDetail from './pages/ProjectDetail'
import Studio from './pages/Studio'
import VoiceCloning from './components/VoiceCloning'
import SettingsPage from './components/SettingsPage'
import ProfilePage from './components/ProfilePage'
import LoginPage from './components/LoginPage'
import RegisterPage from './components/RegisterPage'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import { Toaster } from '@/components/ui/sonner'
import './App.css'

// Protected Route Component
const ProtectedRoute = ({ children }) => {
  const { user, loading } = useAuth()
  const location = useLocation()

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-500"></div>
      </div>
    )
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return children
}

// Public Route Component (redirects logged in users)
const PublicRoute = ({ children }) => {
  const { user, loading } = useAuth()
  const location = useLocation()

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-500"></div>
      </div>
    )
  }

  if (user) {
    const from = location.state?.from?.pathname || "/dashboard"
    return <Navigate to={from} replace />
  }

  return children
}

function AppContent() {
  const navigate = useNavigate()

  return (
    <Routes>
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route 
        path="/login" 
        element={
          <PublicRoute>
            <LoginPage />
          </PublicRoute>
        } 
      />
      <Route 
        path="/register" 
        element={
          <PublicRoute>
            <RegisterPage />
          </PublicRoute>
        } 
      />
      <Route 
        path="/dashboard" 
        element={
          <ProtectedRoute>
            <Dashboard />
          </ProtectedRoute>
        } 
      />
      <Route path="/create" element={<Navigate to="/studio" replace />} />
      <Route
        path="/studio"
        element={
          <ProtectedRoute>
            <Studio />
          </ProtectedRoute>
        }
      />
      <Route
        path="/studio/:projectId"
        element={
          <ProtectedRoute>
            <Studio />
          </ProtectedRoute>
        }
      />
      <Route 
        path="/projects/:id" 
        element={
          <ProtectedRoute>
            <ProjectDetail />
          </ProtectedRoute>
        } 
      />
      <Route 
        path="/settings" 
        element={
          <ProtectedRoute>
            <SettingsPage />
          </ProtectedRoute>
        } 
      />
      <Route 
        path="/profile" 
        element={
          <ProtectedRoute>
            <ProfilePage />
          </ProtectedRoute>
        } 
      />
      <Route 
        path="/voice-cloning" 
        element={
          <ProtectedRoute>
            <VoiceCloning />
          </ProtectedRoute>
        } 
      />
      <Route path="*" element={
        <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
          <div className="text-center text-white">
            <h1 className="text-4xl font-bold mb-2">404</h1>
            <p className="text-slate-300 mb-4">Page not found</p>
            <a href="/dashboard" className="text-purple-400 hover:text-purple-300">Back to dashboard</a>
          </div>
        </div>
      } />
    </Routes>
  )
}

function App() {
  return (
    <AuthProvider>
      <Router>
        <AppContent />
      </Router>
      <Toaster />
    </AuthProvider>
  )
}

export default App
