/**
 * React Query hooks for pull history
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchPullHistory, triggerManualPull, ManualPullRequest } from '@/api'

export function usePullHistory(params: {
  page?: number
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
