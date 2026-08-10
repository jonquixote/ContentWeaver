import { createContext, useContext, useState, useEffect } from 'react'
import api from '@/services/api'

const AuthContext = createContext()

export const useAuth = () => {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Check if user is logged in by verifying the token with the backend
    const checkAuthStatus = async () => {
      const token = localStorage.getItem('authToken')
      if (token) {
        try {
          // In a real app, you would verify the token with the backend
          // For now, we'll just set a user based on the token existing
          // In a more complete implementation, we would make an API call to verify the token
          const response = await api.request('/auth/me', {
            method: 'GET',
            headers: {
              'Authorization': `Bearer ${token}`
            }
          })
          setUser(response)
        } catch (error) {
          console.error('Failed to verify token:', error)
          localStorage.removeItem('authToken')
        }
      }
      setLoading(false)
    }
    
    checkAuthStatus()
  }, [])

  const login = async (credentials) => {
    try {
      const response = await api.login(credentials)
      const { user, token } = response
      setUser(user)
      api.setToken(token)
      return user
    } catch (error) {
      throw error
    }
  }

  const logout = async () => {
    try {
      await api.logout()
    } catch (error) {
      console.error('Logout error:', error)
    } finally {
      setUser(null)
      api.setToken(null)
    }
  }

  const register = async (userData) => {
    try {
      const response = await api.register({
        username: userData.name,
        email: userData.email,
        password: userData.password
      })
      const { user, token } = response
      setUser(user)
      api.setToken(token)
      return user
    } catch (error) {
      throw error
    }
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