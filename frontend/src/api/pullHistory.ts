/**
 * API functions for Pull History
 */

import { apiClient } from './client'
import type {
  PaginatedResponse,
  PullHistory,
  ManualPullRequest,
  ManualPullResponse,
  InitialPullRequest,
  InitialPullResponse,
} from './types'

/**
 * Fetch paginated list of pull history
 */
export async function fetchPullHistory(params: {
  page?: number
  page_size?: number
  status?: string
  trigger_type?: string
  tenant?: number
} = {}): Promise<PaginatedResponse<PullHistory>> {
  const response = await apiClient.get<PaginatedResponse<PullHistory>>(
    '/pull-history/',
    { params }
  )
  return response.data
}

/**
 * Trigger a manual pull
 */
export async function triggerManualPull(
  data: ManualPullRequest
): Promise<ManualPullResponse> {
  const response = await apiClient.post<ManualPullResponse>(
    '/manual-pull/',
    data
  )
  return response.data
}

/**
 * Trigger an initial full historical pull (10 days)
 */
export async function triggerInitialPull(
  data: InitialPullRequest
): Promise<InitialPullResponse> {
  const response = await apiClient.post<InitialPullResponse>(
    '/initial-pull/',
    data
  )
  return response.data
}
