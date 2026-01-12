/**
 * API functions for Message Traces
 */

import { apiClient } from './client'
import type {
  PaginatedResponse,
  MessageTraceLog,
  TraceFilterParams,
} from './types'

/**
 * Fetch paginated list of message traces with optional filters
 */
export async function fetchTraces(
  params: TraceFilterParams = {}
): Promise<PaginatedResponse<MessageTraceLog>> {
  const response = await apiClient.get<PaginatedResponse<MessageTraceLog>>(
    '/traces/',
    { params }
  )
  return response.data
}

/**
 * Fetch a single message trace by ID
 */
export async function fetchTrace(id: number): Promise<MessageTraceLog> {
  const response = await apiClient.get<MessageTraceLog>(`/traces/${id}/`)
  return response.data
}
