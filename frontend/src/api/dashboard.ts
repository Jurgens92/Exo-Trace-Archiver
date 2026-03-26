/**
 * API functions for Dashboard and Config
 */

import { apiClient } from './client'
import type { DashboardStats, ConfigResponse, AuthTokenResponse } from './types'

/**
 * Fetch dashboard statistics, optionally filtered by tenant
 */
export async function fetchDashboardStats(tenantId?: number): Promise<DashboardStats> {
  const params = tenantId ? { tenant: tenantId } : undefined
  const response = await apiClient.get<DashboardStats>('/dashboard/', { params })
  return response.data
}

/**
 * Fetch current configuration (sanitized)
 */
export async function fetchConfig(): Promise<ConfigResponse> {
  const response = await apiClient.get<ConfigResponse>('/config/')
  return response.data
}

/**
 * Authenticate and get token
 */
export async function login(
  username: string,
  password: string
): Promise<AuthTokenResponse> {
  const response = await apiClient.post<AuthTokenResponse>('/auth/token/', {
    username,
    password,
  })
  return response.data
}
