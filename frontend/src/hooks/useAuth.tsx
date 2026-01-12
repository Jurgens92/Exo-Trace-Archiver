/**
 * Authentication hook and context provider with user info
 */

import {
  createContext,
  useContext,
  useState,
  useEffect,
  ReactNode,
} from 'react'
import { login as apiLogin, getAuthToken, setAuthToken, clearAuthToken, getCurrentUser } from '@/api'
import type { CurrentUser } from '@/api'

interface AuthContextType {
  isAuthenticated: boolean
  isLoading: boolean
  user: CurrentUser | null
  isAdmin: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  refreshUser: () => Promise<void>
  error: string | null
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [user, setUser] = useState<CurrentUser | null>(null)
  const [error, setError] = useState<string | null>(null)

  const fetchUser = async () => {
    try {
      const userData = await getCurrentUser()
      setUser(userData)
      return userData
    } catch {
      // If fetching user fails, clear auth state
      clearAuthToken()
      setIsAuthenticated(false)
      setUser(null)
      return null
    }
  }

  // Check for existing token on mount and fetch user info
  useEffect(() => {
    const initAuth = async () => {
      const token = getAuthToken()
      if (token) {
        setIsAuthenticated(true)
        await fetchUser()
      }
      setIsLoading(false)
    }
    initAuth()
  }, [])

  const login = async (username: string, password: string) => {
    setIsLoading(true)
    setError(null)

    try {
      const response = await apiLogin(username, password)
      setAuthToken(response.token)
      setIsAuthenticated(true)
      await fetchUser()
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Login failed'
      setError(message)
      throw err
    } finally {
      setIsLoading(false)
    }
  }

  const logout = () => {
    clearAuthToken()
    setIsAuthenticated(false)
    setUser(null)
  }

  const refreshUser = async () => {
    await fetchUser()
  }

  const isAdmin = user?.is_admin ?? false

  return (
    <AuthContext.Provider
      value={{ isAuthenticated, isLoading, user, isAdmin, login, logout, refreshUser, error }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
