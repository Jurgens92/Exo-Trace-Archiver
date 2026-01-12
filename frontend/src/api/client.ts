/**
 * API Client for Exo-Trace-Archiver backend
 *
 * Uses axios for HTTP requests with automatic token handling
 * and error transformation.
 */

import axios, { AxiosError } from 'axios'

// API base URL - uses Vite proxy in development
const API_BASE_URL = '/api'

// Create axios instance with default configuration
export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Token storage key
const TOKEN_KEY = 'exo_trace_token'

// Get stored auth token
export function getAuthToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

// Set auth token
export function setAuthToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

// Clear auth token
export function clearAuthToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

// Request interceptor to add auth token
apiClient.interceptors.request.use(
  (config) => {
    const token = getAuthToken()
    if (token) {
      config.headers.Authorization = `Token ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      // Clear token and redirect to login on 401
      clearAuthToken()
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// API Error type
export interface ApiError {
  message: string
  detail?: string
  status?: number
}

// Transform axios error to ApiError
export function transformError(error: unknown): ApiError {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<{ detail?: string; message?: string }>
    return {
      message: axiosError.response?.data?.detail ||
               axiosError.response?.data?.message ||
               axiosError.message ||
               'An error occurred',
      detail: axiosError.response?.data?.detail,
      status: axiosError.response?.status,
    }
  }
  return {
    message: error instanceof Error ? error.message : 'An unknown error occurred',
  }
}
