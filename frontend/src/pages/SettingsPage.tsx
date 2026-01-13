import { RefreshCw, Play, Check, X, AlertCircle, AlertTriangle } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { useConfig } from '@/hooks/useDashboard'
import { useManualPull } from '@/hooks/usePullHistory'
import { LoadingPage, LoadingSpinner } from '@/components/LoadingSpinner'
import { useToast } from '@/components/ui/use-toast'
import { useTenantContext } from '@/hooks/useTenantContext'
import { useQuery } from '@tanstack/react-query'
import { getTenant } from '@/api/tenants'

export function SettingsPage() {
  const { data: config, isLoading, error, refetch } = useConfig()
  const manualPull = useManualPull()
  const { toast } = useToast()
  const { selectedTenant, hasTenantSelected } = useTenantContext()

  // Fetch full tenant details when a tenant is selected
  const { data: tenantDetails, isLoading: tenantLoading } = useQuery({
    queryKey: ['tenant', selectedTenant?.id],
    queryFn: () => getTenant(selectedTenant!.id),
    enabled: hasTenantSelected,
  })

  const handleManualPull = async () => {
    if (!selectedTenant) {
      toast({
        title: 'No tenant selected',
        description: 'Please select a tenant from the sidebar before pulling traces.',
        variant: 'destructive',
      })
      return
    }

    try {
      const result = await manualPull.mutateAsync({ tenant_id: selectedTenant.id })
      toast({
        title: 'Pull completed',
        description: `Pulled ${result.records_pulled} records (${result.records_new} new) for ${result.tenant_name}`,
      })
    } catch {
      toast({
        title: 'Pull failed',
        description: 'Failed to execute manual pull. Check the console for details.',
        variant: 'destructive',
      })
    }
  }

  if (isLoading) return <LoadingPage />

  if (error) {
    return (
      <div className="space-y-6">
        <h1 className="text-3xl font-bold">Settings</h1>
        <Card>
          <CardContent className="py-12 text-center">
            <AlertCircle className="h-12 w-12 text-destructive mx-auto mb-4" />
            <p className="text-destructive mb-4">
              Failed to load configuration. You may not have admin permissions.
            </p>
            <Button onClick={() => refetch()}>Retry</Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (!config) return null

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Settings</h1>
        <Button variant="outline" onClick={() => refetch()}>
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Manual Pull Card */}
      <Card>
        <CardHeader>
          <CardTitle>Manual Pull</CardTitle>
          <CardDescription>
            Trigger an on-demand pull of message traces from Microsoft 365
          </CardDescription>
        </CardHeader>
        <CardContent>
          {!hasTenantSelected ? (
            <div className="flex items-center gap-3 p-3 bg-amber-50 dark:bg-amber-950 border border-amber-200 dark:border-amber-800 rounded-md">
              <AlertTriangle className="h-5 w-5 text-amber-600 dark:text-amber-400 flex-shrink-0" />
              <p className="text-sm text-amber-800 dark:text-amber-200">
                Select a tenant from the sidebar to enable manual pulls.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              <div className="flex items-center gap-4">
                <Button
                  onClick={handleManualPull}
                  disabled={manualPull.isPending}
                >
                  {manualPull.isPending ? (
                    <>
                      <LoadingSpinner size="sm" className="mr-2" />
                      Pulling...
                    </>
                  ) : (
                    <>
                      <Play className="h-4 w-4 mr-2" />
                      Pull Now
                    </>
                  )}
                </Button>
                <p className="text-sm text-muted-foreground">
                  Pulls yesterday's message traces for <span className="font-medium">{selectedTenant.name}</span>
                </p>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Tenant Configuration - shows selected tenant's config */}
      <Card>
        <CardHeader>
          <CardTitle>
            {hasTenantSelected
              ? `${selectedTenant.name} Configuration`
              : 'Tenant Configuration'}
          </CardTitle>
          <CardDescription>
            {hasTenantSelected
              ? 'Azure AD app registration and authentication settings for the selected tenant'
              : 'Select a tenant to view its configuration'}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {!hasTenantSelected ? (
            <p className="text-sm text-muted-foreground">
              No tenant selected. Choose a tenant from the sidebar to see its configuration.
            </p>
          ) : tenantLoading ? (
            <div className="flex items-center gap-2">
              <LoadingSpinner size="sm" />
              <span className="text-sm text-muted-foreground">Loading tenant configuration...</span>
            </div>
          ) : tenantDetails ? (
            <div className="grid gap-4 md:grid-cols-2">
              <ConfigItem
                label="Tenant ID"
                value={tenantDetails.tenant_id}
              />
              <ConfigItem
                label="Client ID"
                value={tenantDetails.client_id_masked ?? 'Not configured'}
              />
              <ConfigItem
                label="Auth Method"
                value={tenantDetails.auth_method}
              />
              <ConfigItem
                label="API Method"
                value={tenantDetails.api_method}
              />
              <ConfigItem
                label="Organization"
                value={tenantDetails.organization || 'Not set'}
              />
              <ConfigItem
                label="Certificate"
                value={tenantDetails.has_certificate ?? false}
                type="boolean"
              />
              <ConfigItem
                label="Client Secret"
                value={tenantDetails.has_client_secret ?? false}
                type="boolean"
              />
              <ConfigItem
                label="Status"
                value={tenantDetails.is_active}
                type="boolean"
                trueLabel="Active"
                falseLabel="Inactive"
              />
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              Unable to load tenant configuration.
            </p>
          )}
        </CardContent>
      </Card>

      {/* Message Trace Settings */}
      <Card>
        <CardHeader>
          <CardTitle>Message Trace Settings</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <ConfigItem
              label="Lookback Days"
              value={config.message_trace.lookback_days}
            />
            <ConfigItem
              label="Page Size"
              value={config.message_trace.page_size}
            />
          </div>
        </CardContent>
      </Card>

      {/* Scheduler Settings */}
      <Card>
        <CardHeader>
          <CardTitle>Scheduler Settings</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <ConfigItem
              label="Daily Pull Time (UTC)"
              value={`${config.scheduler.daily_pull_hour.toString().padStart(2, '0')}:${config.scheduler.daily_pull_minute.toString().padStart(2, '0')}`}
            />
            <ConfigItem
              label="Database Engine"
              value={config.database.engine}
            />
          </div>
        </CardContent>
      </Card>

      {/* Debug Mode Warning */}
      {config.debug_mode && (
        <Card className="border-destructive">
          <CardHeader>
            <CardTitle className="text-destructive flex items-center gap-2">
              <AlertCircle className="h-5 w-5" />
              Debug Mode Enabled
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              Debug mode is currently enabled. This should be disabled in production
              environments for security reasons.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

interface ConfigItemProps {
  label: string
  value: string | number | boolean
  type?: 'text' | 'boolean'
  trueLabel?: string
  falseLabel?: string
}

function ConfigItem({ label, value, type = 'text', trueLabel = 'Configured', falseLabel = 'Not configured' }: ConfigItemProps) {
  return (
    <div className="space-y-1">
      <p className="text-sm font-medium text-muted-foreground">{label}</p>
      {type === 'boolean' ? (
        <div className="flex items-center gap-2">
          {value ? (
            <>
              <Check className="h-4 w-4 text-green-500" />
              <span>{trueLabel}</span>
            </>
          ) : (
            <>
              <X className="h-4 w-4 text-muted-foreground" />
              <span className="text-muted-foreground">{falseLabel}</span>
            </>
          )}
        </div>
      ) : (
        <p className="font-mono text-sm bg-muted px-2 py-1 rounded">
          {String(value)}
        </p>
      )}
    </div>
  )
}
