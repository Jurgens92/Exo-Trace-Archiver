/**
 * API functions for application settings
 */

import { apiClient } from './client'

export interface AppSettings {
  domain_discovery_auto_refresh: boolean
  domain_discovery_refresh_hours: number
  scheduled_pull_enabled: boolean
  scheduled_pull_hour: number
  scheduled_pull_minute: number
  updated_at: string
  updated_by_username: string | null
}

export interface UpdateAppSettingsRequest {
  domain_discovery_auto_refresh?: boolean
  domain_discovery_refresh_hours?: number
  scheduled_pull_enabled?: boolean
  scheduled_pull_hour?: number
  scheduled_pull_minute?: number
}

export interface UpdateAppSettingsResponse {
  message: string
  settings: AppSettings
}

/**
 * Get current application settings
 */
export async function getAppSettings(): Promise<AppSettings> {
  const response = await apiClient.get<AppSettings>('/accounts/settings/')
  return response.data
}

/**
 * Update application settings (partial update)
 */
export async function updateAppSettings(
  updates: UpdateAppSettingsRequest
): Promise<UpdateAppSettingsResponse> {
  const response = await apiClient.patch<UpdateAppSettingsResponse>(
    '/accounts/settings/',
    updates
  )
  return response.data
}
