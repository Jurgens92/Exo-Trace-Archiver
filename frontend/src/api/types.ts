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
  tenant?: number
  tenant_name?: string
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
  tenant?: number
  tenant_name?: string
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
  tenant_count?: number
  accessible_tenants?: { id: number; name: string }[]
}

// Manual pull request
export interface ManualPullRequest {
  tenant_id: number
  start_date?: string
  end_date?: string
}

// Manual pull response
export interface ManualPullResponse {
  message: string
  tenant_id: number
  tenant_name: string
  pull_history_id: number
  records_pulled: number
  records_new: number
  status: string
  error?: string
  detail?: string
}

// Config response
export interface ConfigResponse {
  multi_tenant: {
    enabled: boolean
    tenant_count: number
    tenants: {
      id: number
      name: string
      is_active: boolean
      organization: string
    }[]
  }
  legacy_microsoft365?: {
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

// User roles
export type UserRole = 'admin' | 'user'

// User types
export interface User {
  id: number
  username: string
  email: string
  first_name: string
  last_name: string
  is_active: boolean
  date_joined: string
  last_login: string | null
  role: UserRole
  is_admin: boolean
  tenant_count?: number
  tenant_permissions?: TenantPermissionInfo[]
}

export interface TenantPermissionInfo {
  id: number
  tenant_id: number
  tenant_name: string
  granted_at: string
}

export interface UserCreate {
  username: string
  email: string
  password: string
  password_confirm: string
  first_name?: string
  last_name?: string
  role?: UserRole
}

export interface UserUpdate {
  email?: string
  first_name?: string
  last_name?: string
  is_active?: boolean
  role?: UserRole
  password?: string
}

// Tenant types
export interface Tenant {
  id: number
  name: string
  tenant_id: string
  client_id?: string
  client_id_masked?: string
  organization: string
  auth_method: 'certificate' | 'secret'
  api_method: 'graph' | 'powershell'
  certificate_path?: string
  certificate_thumbprint?: string
  has_client_secret?: boolean
  has_certificate?: boolean
  is_active: boolean
  created_at: string
  updated_at?: string
  created_by?: number
  created_by_username?: string
  user_count?: number
}

export interface TenantCreate {
  name: string
  tenant_id: string
  client_id: string
  auth_method: 'certificate' | 'secret'
  client_secret?: string
  certificate_path?: string
  certificate_thumbprint?: string
  certificate_password?: string
  api_method: 'graph' | 'powershell'
  organization?: string
  is_active?: boolean
}

export interface TenantUpdate {
  name?: string
  client_id?: string
  auth_method?: 'certificate' | 'secret'
  client_secret?: string
  certificate_path?: string
  certificate_thumbprint?: string
  certificate_password?: string
  api_method?: 'graph' | 'powershell'
  organization?: string
  is_active?: boolean
}

// Tenant permission types
export interface TenantPermission {
  id: number
  user: number
  user_username: string
  user_email: string
  tenant: number
  tenant_name: string
  granted_at: string
  granted_by: number | null
  granted_by_username: string | null
}

// Current user type (with accessible tenants)
export interface CurrentUser {
  id: number
  username: string
  email: string
  first_name: string
  last_name: string
  role: UserRole
  is_admin: boolean
  accessible_tenants: {
    id: number
    name: string
    organization: string
  }[]
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
  tenant?: number
  page?: number
  page_size?: number
  ordering?: string
}
