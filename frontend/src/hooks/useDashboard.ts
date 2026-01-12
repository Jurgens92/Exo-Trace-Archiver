/**
 * React Query hooks for dashboard and config
 */

import { useQuery } from '@tanstack/react-query'
import { fetchDashboardStats, fetchConfig } from '@/api'

export function useDashboard() {
  return useQuery({
    queryKey: ['dashboard'],
    queryFn: fetchDashboardStats,
    refetchInterval: 1000 * 60 * 5, // Refresh every 5 minutes
  })
}

export function useConfig() {
  return useQuery({
    queryKey: ['config'],
    queryFn: fetchConfig,
  })
}
