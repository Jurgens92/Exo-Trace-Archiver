/**
 * Hook for managing application settings
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getAppSettings, updateAppSettings, UpdateAppSettingsRequest } from '@/api/settings'
import { transformError } from '@/api/client'

/**
 * Hook to fetch and cache application settings
 */
export function useAppSettings() {
  return useQuery({
    queryKey: ['appSettings'],
    queryFn: getAppSettings,
    staleTime: 5 * 60 * 1000, // Cache for 5 minutes
  })
}

/**
 * Hook to update application settings
 */
export function useUpdateAppSettings() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (updates: UpdateAppSettingsRequest) => updateAppSettings(updates),
    onSuccess: (data) => {
      // Update the cache with the new settings
      queryClient.setQueryData(['appSettings'], data.settings)
    },
    onError: (error) => {
      const apiError = transformError(error)
      console.error('Failed to update settings:', apiError)
    },
  })
}
