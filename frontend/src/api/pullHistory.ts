/**
 * API functions for Pull History
 */

import { apiClient } from './client'
import type {
  PaginatedResponse,
  PullHistory,
  ManualPullRequest,
  ManualPullResponse,
} from './types'

/**
 * Fetch paginated list of pull history
 */
export async function fetchPullHistory(params: {
  page?: number
  status?: string
  trigger_type?: string
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
  data: ManualPullRequest = {}
): Promise<ManualPullResponse> {
  const response = await apiClient.post<ManualPullResponse>(
    '/manual-pull/',
    data
  )
  return response.data
}
