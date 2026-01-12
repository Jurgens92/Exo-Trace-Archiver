/**
 * User management API functions
 */

import { apiClient } from './client'
import type {
  User,
  UserCreate,
  UserUpdate,
  CurrentUser,
  PaginatedResponse,
  TenantPermission,
} from './types'

// Get current user info
export async function getCurrentUser(): Promise<CurrentUser> {
  const response = await apiClient.get<CurrentUser>('/accounts/me/')
  return response.data
}

// Update current user profile
export async function updateCurrentUser(data: Partial<UserUpdate>): Promise<CurrentUser> {
  const response = await apiClient.patch<CurrentUser>('/accounts/me/', data)
  return response.data
}

// Get list of users (admin only)
export async function getUsers(params?: {
  search?: string
  page?: number
  ordering?: string
}): Promise<PaginatedResponse<User>> {
  const response = await apiClient.get<PaginatedResponse<User>>('/accounts/users/', { params })
  return response.data
}

// Get single user (admin only)
export async function getUser(id: number): Promise<User> {
  const response = await apiClient.get<User>(`/accounts/users/${id}/`)
  return response.data
}

// Create user (admin only)
export async function createUser(data: UserCreate): Promise<User> {
  const response = await apiClient.post<User>('/accounts/users/', data)
  return response.data
}

// Update user (admin only)
export async function updateUser(id: number, data: UserUpdate): Promise<User> {
  const response = await apiClient.patch<User>(`/accounts/users/${id}/`, data)
  return response.data
}

// Delete user (admin only)
export async function deleteUser(id: number): Promise<void> {
  await apiClient.delete(`/accounts/users/${id}/`)
}

// Set user role (admin only)
export async function setUserRole(id: number, role: 'admin' | 'user'): Promise<{ detail: string }> {
  const response = await apiClient.post<{ detail: string }>(
    `/accounts/users/${id}/set_role/`,
    { role }
  )
  return response.data
}

// Get user's tenant permissions (admin only)
export async function getUserTenantPermissions(userId: number): Promise<TenantPermission[]> {
  const response = await apiClient.get<TenantPermission[]>(
    `/accounts/users/${userId}/tenant_permissions/`
  )
  return response.data
}

// Add tenant permissions for user (admin only)
export async function addUserTenantPermissions(
  userId: number,
  tenantIds: number[]
): Promise<{ detail: string; created_tenant_ids: number[] }> {
  const response = await apiClient.post<{ detail: string; created_tenant_ids: number[] }>(
    `/accounts/users/${userId}/tenant_permissions/`,
    { tenant_ids: tenantIds }
  )
  return response.data
}

// Remove tenant permissions for user (admin only)
export async function removeUserTenantPermissions(
  userId: number,
  tenantIds: number[]
): Promise<{ detail: string }> {
  const response = await apiClient.delete<{ detail: string }>(
    `/accounts/users/${userId}/tenant_permissions/`,
    { data: { tenant_ids: tenantIds } }
  )
  return response.data
}
