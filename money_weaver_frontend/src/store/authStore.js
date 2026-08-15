import { create } from 'zustand'
import { createJSONStorage, persist } from 'zustand/middleware'

const AUTH_TOKEN_KEY = 'authToken'

export const useAuthStore = create(
  persist(
    (set) => ({
      user: null,
      token: localStorage.getItem(AUTH_TOKEN_KEY) || null,
      loading: true,
      setUser: (user) => set({ user }),
      setToken: (token) => {
        set({ token })
        if (token) {
          localStorage.setItem(AUTH_TOKEN_KEY, token)
        } else {
          localStorage.removeItem(AUTH_TOKEN_KEY)
        }
      },
      setLoading: (loading) => set({ loading }),
      login: ({ user, token }) => {
        set({ user, token })
        if (token) {
          localStorage.setItem(AUTH_TOKEN_KEY, token)
        } else {
          localStorage.removeItem(AUTH_TOKEN_KEY)
        }
      },
      logout: () => {
        set({ user: null, token: null })
        localStorage.removeItem(AUTH_TOKEN_KEY)
      },
      hydrate: ({ user = null, token = null } = {}) => {
        set({ user, token, loading: false })
        if (token) {
          localStorage.setItem(AUTH_TOKEN_KEY, token)
        } else {
          localStorage.removeItem(AUTH_TOKEN_KEY)
        }
      },
    }),
    {
      name: 'auth-storage',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({ user: state.user }),
    },
  ),
)