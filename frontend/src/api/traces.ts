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

/**
 * Export a single message trace as PDF
 * Returns a blob that can be downloaded
 */
export async function exportTracePdf(id: number): Promise<Blob> {
  const response = await apiClient.get(`/traces/${id}/export-pdf/`, {
    responseType: 'blob',
  })
  return response.data
}

/**
 * Export search results as PDF
 * Returns a blob that can be downloaded
 */
export async function exportSearchResultsPdf(
  params: TraceFilterParams = {}
): Promise<Blob> {
  const response = await apiClient.get('/traces/export-search-pdf/', {
    params,
    responseType: 'blob',
  })
  return response.data
}

/**
 * Utility function to download a blob as a file
 */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.URL.revokeObjectURL(url)
}
