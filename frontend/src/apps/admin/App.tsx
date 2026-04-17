import { BrowserRouter, HashRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { queryClient } from '@/lib/query-client'
import { useAuthStore } from '@/stores/auth'
import { Login } from './pages/Login'
import { Dashboard } from './pages/Dashboard'
import { KnowledgeBase } from './pages/KnowledgeBase'
import { AgentConfig } from './pages/AgentConfig'
import { Feedback } from './pages/Feedback'
import { MetricsPage } from './pages/MetricsPage'

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, user } = useAuthStore()
  const isAdmin = user?.role === 'ADMIN'
  return isAuthenticated && isAdmin ? children : <Navigate to="/login" replace />
}

const Router = import.meta.env.DEV ? HashRouter : BrowserRouter

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Router basename={import.meta.env.DEV ? undefined : '/admin'}>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            path="/"
            element={
              <PrivateRoute>
                <Dashboard />
              </PrivateRoute>
            }
          />
          <Route
            path="/knowledge"
            element={
              <PrivateRoute>
                <KnowledgeBase />
              </PrivateRoute>
            }
          />
          <Route
            path="/agent-config"
            element={
              <PrivateRoute>
                <AgentConfig />
              </PrivateRoute>
            }
          />
          <Route
            path="/feedback"
            element={
              <PrivateRoute>
                <Feedback />
              </PrivateRoute>
            }
          />
          <Route
            path="/metrics"
            element={
              <PrivateRoute>
                <MetricsPage />
              </PrivateRoute>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Router>
    </QueryClientProvider>
  )
}

export default App
