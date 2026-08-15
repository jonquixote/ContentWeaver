import { createContext, useContext, useEffect } from 'react'
import api from '@/services/api'
import { useAuthStore } from '@/store/authStore'

const AuthContext = createContext()

export const useAuth = () => {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

export const AuthProvider = ({ children }) => {
  const user = useAuthStore((s) => s.user)
  const loading = useAuthStore((s) => s.loading)

  useEffect(() => {
    // Verify a stored token with the backend, then hydrate the store.
    const checkAuthStatus = async () => {
      const { token } = useAuthStore.getState()
      if (token) {
        try {
          const response = await api.request('/auth/me', {
            method: 'GET',
            headers: {
              'Authorization': `Bearer ${token}`
            }
          })
          useAuthStore.getState().hydrate({ user: response, token })
        } catch (error) {
          console.error('Failed to verify token:', error)
          useAuthStore.getState().hydrate({ user: null, token: null })
        }
      } else {
        useAuthStore.getState().hydrate({ user: null, token: null })
      }
    }

    checkAuthStatus()
  }, [])

  const login = async (credentials) => {
    const response = await api.login(credentials)
    const { user, token } = response
    useAuthStore.getState().setUser(user)
    api.setToken(token)
    return user
  }

  const logout = async () => {
    try {
      await api.logout()
    } catch (error) {
      console.error('Logout error:', error)
    } finally {
      useAuthStore.getState().setUser(null)
      api.setToken(null)
    }
  }

  const register = async (userData) => {
    const response = await api.register({
      username: userData.name,
      email: userData.email,
      password: userData.password
    })
    const { user, token } = response
    useAuthStore.getState().setUser(user)
    api.setToken(token)
    return user
  }

  const value = {
    user,
    login,
    logout,
    register,
    loading
  }

  return (
    <AuthContext.Provider value={value}>
      {!loading && children}
    </AuthContext.Provider>
  )
}