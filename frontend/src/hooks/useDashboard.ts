/**
 * React Query hooks for dashboard and config
 */

import { useQuery } from '@tanstack/react-query'
import { fetchDashboardStats, fetchConfig } from '@/api'

export function useDashboard(tenantId?: number | null) {
  return useQuery({
    queryKey: ['dashboard', tenantId ?? 'all'],
    queryFn: () => fetchDashboardStats(tenantId ?? undefined),
    refetchInterval: 1000 * 60 * 5, // Refresh every 5 minutes
  })
}

export function useConfig() {
  return useQuery({
    queryKey: ['config'],
    queryFn: fetchConfig,
  })
}
