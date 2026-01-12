/**
 * React Query hooks for message traces
 */

import { useQuery } from '@tanstack/react-query'
import { fetchTraces, fetchTrace, TraceFilterParams } from '@/api'

export function useTraces(params: TraceFilterParams = {}) {
  return useQuery({
    queryKey: ['traces', params],
    queryFn: () => fetchTraces(params),
  })
}

export function useTrace(id: number) {
  return useQuery({
    queryKey: ['trace', id],
    queryFn: () => fetchTrace(id),
    enabled: !!id,
  })
}
