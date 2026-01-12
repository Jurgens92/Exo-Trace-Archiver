/**
 * TypeScript types for API responses
 */

// Pagination response wrapper
export interface PaginatedResponse<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

// Message Trace Log
export interface MessageTraceLog {
  id: number
  message_id: string
  received_date: string
  sender: string
  recipient: string
  subject: string
  status: TraceStatus
  direction: TraceDirection
  size: number
  size_formatted: string
  event_data: Record<string, unknown>
  trace_date: string
  created_at: string
  updated_at: string
  raw_json?: Record<string, unknown>
  duration_since_received?: string
}

// Trace status enum
export type TraceStatus =
  | 'Delivered'
  | 'Failed'
  | 'Pending'
  | 'Expanded'
  | 'Quarantined'
  | 'FilteredAsSpam'
  | 'None'
  | 'Unknown'

// Trace direction enum
export type TraceDirection =
  | 'Inbound'
  | 'Outbound'
  | 'Internal'
  | 'Unknown'

// Pull History
export interface PullHistory {
  id: number
  start_time: string
  end_time: string | null
  pull_start_date: string
  pull_end_date: string
  records_pulled: number
  records_new: number
  records_updated: number
  status: PullStatus
  error_message: string
  trigger_type: 'Scheduled' | 'Manual'
  triggered_by: string
  api_method: string
  duration_formatted: string | null
  created_at: string
}

// Pull status enum
export type PullStatus =
  | 'Running'
  | 'Success'
  | 'Partial'
  | 'Failed'
  | 'Cancelled'

// Dashboard stats
export interface DashboardStats {
  total_traces: number
  traces_today: number
  traces_this_week: number
  last_pull: PullHistory | null
  delivered_count: number
  failed_count: number
  pending_count: number
  quarantined_count: number
  inbound_count: number
  outbound_count: number
  internal_count: number
  recent_pulls: PullHistory[]
}

// Manual pull request
export interface ManualPullRequest {
  start_date?: string
  end_date?: string
}

// Manual pull response
export interface ManualPullResponse {
  message: string
  pull_history_id: number
  records_pulled: number
  records_new: number
  status: string
  error?: string
  detail?: string
}

// Config response
export interface ConfigResponse {
  microsoft365: {
    tenant_id: string
    client_id: string
    auth_method: string
    api_method: string
    organization: string
    certificate_configured: boolean
    client_secret_configured: boolean
  }
  message_trace: {
    lookback_days: number
    page_size: number
  }
  scheduler: {
    daily_pull_hour: number
    daily_pull_minute: number
  }
  database: {
    engine: string
  }
  debug_mode: boolean
}

// Auth token response
export interface AuthTokenResponse {
  token: string
}

// Trace filter params
export interface TraceFilterParams {
  search?: string
  start_date?: string
  end_date?: string
  sender?: string
  sender_contains?: string
  recipient?: string
  recipient_contains?: string
  status?: TraceStatus
  direction?: TraceDirection
  page?: number
  page_size?: number
  ordering?: string
}
