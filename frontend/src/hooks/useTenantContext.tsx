/**
 * Tenant context for switching between tenants.
 * Allows admins to filter logs by selected tenant.
 */

import {
  createContext,
  useContext,
  useState,
  useEffect,
  ReactNode,
  useCallback,
} from 'react'
import { useAuth } from './useAuth'

interface TenantInfo {
  id: number
  name: string
  organization: string
}

interface TenantContextType {
  // Available tenants for the current user
  availableTenants: TenantInfo[]
  // Currently selected tenant (null means "All Tenants")
  selectedTenant: TenantInfo | null
  // Select a tenant by ID (null to clear selection)
  selectTenant: (tenantId: number | null) => void
  // Whether a tenant is currently selected
  hasTenantSelected: boolean
  // Loading state
  isLoading: boolean
}

const TenantContext = createContext<TenantContextType | undefined>(undefined)

const STORAGE_KEY = 'selectedTenantId'

export function TenantProvider({ children }: { children: ReactNode }) {
  const { user, isAuthenticated } = useAuth()
  const [selectedTenant, setSelectedTenant] = useState<TenantInfo | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const availableTenants = user?.accessible_tenants ?? []

  // Load selected tenant from localStorage on mount
  useEffect(() => {
    if (!isAuthenticated || !user) {
      setIsLoading(false)
      return
    }

    const storedTenantId = localStorage.getItem(STORAGE_KEY)
    if (storedTenantId) {
      const tenantId = parseInt(storedTenantId, 10)
      const tenant = availableTenants.find((t) => t.id === tenantId)
      if (tenant) {
        setSelectedTenant(tenant)
      } else {
        // Stored tenant not accessible anymore, clear it
        localStorage.removeItem(STORAGE_KEY)
      }
    }
    setIsLoading(false)
  }, [isAuthenticated, user, availableTenants])

  const selectTenant = useCallback(
    (tenantId: number | null) => {
      if (tenantId === null) {
        setSelectedTenant(null)
        localStorage.removeItem(STORAGE_KEY)
      } else {
        const tenant = availableTenants.find((t) => t.id === tenantId)
        if (tenant) {
          setSelectedTenant(tenant)
          localStorage.setItem(STORAGE_KEY, tenantId.toString())
        }
      }
    },
    [availableTenants]
  )

  return (
    <TenantContext.Provider
      value={{
        availableTenants,
        selectedTenant,
        selectTenant,
        hasTenantSelected: selectedTenant !== null,
        isLoading,
      }}
    >
      {children}
    </TenantContext.Provider>
  )
}

export function useTenantContext(): TenantContextType {
  const context = useContext(TenantContext)
  if (context === undefined) {
    throw new Error('useTenantContext must be used within a TenantProvider')
  }
  return context
}
