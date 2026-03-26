/**
 * React Query hooks for pull history
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchPullHistory, triggerManualPull, triggerInitialPull, ManualPullRequest, InitialPullRequest } from '@/api'

export function usePullHistory(params: {
  page?: number
  page_size?: number
  status?: string
  trigger_type?: string
} = {}) {
  return useQuery({
    queryKey: ['pullHistory', params],
    queryFn: () => fetchPullHistory(params),
  })
}

export function useManualPull() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: ManualPullRequest) => triggerManualPull(data),
    onSuccess: () => {
      // Invalidate relevant queries after successful pull
      queryClient.invalidateQueries({ queryKey: ['pullHistory'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      queryClient.invalidateQueries({ queryKey: ['traces'] })
    },
  })
}

export function useInitialPull() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: InitialPullRequest) => triggerInitialPull(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pullHistory'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      queryClient.invalidateQueries({ queryKey: ['traces'] })
      queryClient.invalidateQueries({ queryKey: ['tenant'] })
    },
  })
}
