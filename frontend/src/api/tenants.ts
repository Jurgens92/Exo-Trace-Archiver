/**
 * Tenant management API functions
 */

import { apiClient } from './client'
import type {
  Tenant,
  TenantCreate,
  TenantUpdate,
  TenantPermission,
  PaginatedResponse,
} from './types'

// Get list of tenants accessible to current user
export async function getAccessibleTenants(): Promise<Tenant[]> {
  const response = await apiClient.get<Tenant[]>('/accounts/me/tenants/')
  return response.data
}

// Get list of all tenants (admin only)
export async function getTenants(params?: {
  search?: string
  is_active?: boolean
  page?: number
  ordering?: string
}): Promise<PaginatedResponse<Tenant>> {
  const response = await apiClient.get<PaginatedResponse<Tenant>>('/accounts/tenants/', { params })
  return response.data
}

// Get single tenant (admin only)
export async function getTenant(id: number): Promise<Tenant> {
  const response = await apiClient.get<Tenant>(`/accounts/tenants/${id}/`)
  return response.data
}

// Create tenant (admin only)
export async function createTenant(data: TenantCreate): Promise<Tenant> {
  const response = await apiClient.post<Tenant>('/accounts/tenants/', data)
  return response.data
}

// Update tenant (admin only)
export async function updateTenant(id: number, data: TenantUpdate): Promise<Tenant> {
  const response = await apiClient.patch<Tenant>(`/accounts/tenants/${id}/`, data)
  return response.data
}

// Delete tenant (admin only)
export async function deleteTenant(id: number): Promise<void> {
  await apiClient.delete(`/accounts/tenants/${id}/`)
}

// Get users with access to tenant (admin only)
export async function getTenantUsers(tenantId: number): Promise<TenantPermission[]> {
  const response = await apiClient.get<TenantPermission[]>(
    `/accounts/tenants/${tenantId}/users/`
  )
  return response.data
}

// Add users to tenant (admin only)
export async function addTenantUsers(
  tenantId: number,
  userIds: number[]
): Promise<{ detail: string; created_user_ids: number[]; skipped: { id: number; reason: string }[] }> {
  const response = await apiClient.post<{
    detail: string
    created_user_ids: number[]
    skipped: { id: number; reason: string }[]
  }>(`/accounts/tenants/${tenantId}/add_users/`, { user_ids: userIds })
  return response.data
}

// Remove users from tenant (admin only)
export async function removeTenantUsers(
  tenantId: number,
  userIds: number[]
): Promise<{ detail: string }> {
  const response = await apiClient.post<{ detail: string }>(
    `/accounts/tenants/${tenantId}/remove_users/`,
    { user_ids: userIds }
  )
  return response.data
}

// Test tenant connection (admin only)
export async function testTenantConnection(
  tenantId: number
): Promise<{ status: string; detail: string }> {
  const response = await apiClient.post<{ status: string; detail: string }>(
    `/accounts/tenants/${tenantId}/test_connection/`
  )
  return response.data
}
