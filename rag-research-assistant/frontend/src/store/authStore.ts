import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { User } from '@/types'
import { authAPI } from '@/services/api'

interface AuthState {
  user: User | null
  accessToken: string | null
  refreshToken: string | null
  isAuthenticated: boolean
  isLoading: boolean

  login: (email: string, password: string) => Promise<void>
  signup: (data: { email: string; username: string; password: string; full_name?: string }) => Promise<void>
  logout: () => void
  fetchMe: () => Promise<void>
  updateUser: (updates: Partial<User>) => void
  setTokens: (access: string, refresh: string) => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,
      isLoading: false,

      setTokens: (access, refresh) => {
        localStorage.setItem('access_token', access)
        localStorage.setItem('refresh_token', refresh)
        set({ accessToken: access, refreshToken: refresh, isAuthenticated: true })
      },

      login: async (email, password) => {
        set({ isLoading: true })
        try {
          const { data } = await authAPI.login({ email, password })
          localStorage.setItem('access_token', data.access_token)
          localStorage.setItem('refresh_token', data.refresh_token)
          set({
            accessToken: data.access_token,
            refreshToken: data.refresh_token,
            isAuthenticated: true,
          })
          // Fetch user profile
          const { data: user } = await authAPI.getMe()
          set({ user, isLoading: false })
        } catch (err) {
          set({ isLoading: false })
          throw err
        }
      },

      signup: async (data) => {
        set({ isLoading: true })
        try {
          await authAPI.signup(data)
          // Auto-login after signup
          await get().login(data.email, data.password)
        } catch (err) {
          set({ isLoading: false })
          throw err
        }
      },

      logout: () => {
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        set({ user: null, accessToken: null, refreshToken: null, isAuthenticated: false })
      },

      fetchMe: async () => {
        try {
          const { data } = await authAPI.getMe()
          set({ user: data, isAuthenticated: true })
        } catch {
          get().logout()
        }
      },

      updateUser: (updates) => {
        const current = get().user
        if (current) set({ user: { ...current, ...updates } })
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        isAuthenticated: state.isAuthenticated,
        user: state.user,
      }),
    },
  ),
)
