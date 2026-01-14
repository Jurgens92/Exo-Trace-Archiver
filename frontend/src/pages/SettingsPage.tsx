import { RefreshCw, Play, Check, X, AlertCircle, AlertTriangle, Save, Settings2 } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { useConfig } from '@/hooks/useDashboard'
import { useManualPull } from '@/hooks/usePullHistory'
import { LoadingPage, LoadingSpinner } from '@/components/LoadingSpinner'
import { useToast } from '@/components/ui/use-toast'
import { useTenantContext } from '@/hooks/useTenantContext'
import { useQuery } from '@tanstack/react-query'
import { getTenant } from '@/api/tenants'
import { useAppSettings, useUpdateAppSettings } from '@/hooks/useAppSettings'
import { useState, useEffect } from 'react'
import { AppSettings } from '@/api/settings'

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

  // App settings state
  const { data: appSettings, isLoading: settingsLoading } = useAppSettings()
  const updateSettings = useUpdateAppSettings()
  const [localSettings, setLocalSettings] = useState<AppSettings | null>(null)
  const [hasChanges, setHasChanges] = useState(false)

  // Initialize local settings when app settings are loaded
  useEffect(() => {
    if (appSettings) {
      setLocalSettings(appSettings)
      setHasChanges(false)
    }
  }, [appSettings])

  // Check if settings have changed
  useEffect(() => {
    if (localSettings && appSettings) {
      const changed =
        localSettings.domain_discovery_auto_refresh !== appSettings.domain_discovery_auto_refresh ||
        localSettings.domain_discovery_refresh_hours !== appSettings.domain_discovery_refresh_hours ||
        localSettings.scheduled_pull_enabled !== appSettings.scheduled_pull_enabled ||
        localSettings.scheduled_pull_hour !== appSettings.scheduled_pull_hour ||
        localSettings.scheduled_pull_minute !== appSettings.scheduled_pull_minute
      setHasChanges(changed)
    }
  }, [localSettings, appSettings])

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

  const handleSaveSettings = async () => {
    if (!localSettings) return

    try {
      const result = await updateSettings.mutateAsync({
        domain_discovery_auto_refresh: localSettings.domain_discovery_auto_refresh,
        domain_discovery_refresh_hours: localSettings.domain_discovery_refresh_hours,
        scheduled_pull_enabled: localSettings.scheduled_pull_enabled,
        scheduled_pull_hour: localSettings.scheduled_pull_hour,
        scheduled_pull_minute: localSettings.scheduled_pull_minute,
      })
      toast({
        title: 'Settings saved',
        description: result.message || 'Application settings updated successfully.',
      })
      setHasChanges(false)
    } catch (error) {
      toast({
        title: 'Failed to save settings',
        description: 'An error occurred while saving settings. Please try again.',
        variant: 'destructive',
      })
    }
  }

  const handleResetSettings = () => {
    if (appSettings) {
      setLocalSettings(appSettings)
      setHasChanges(false)
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

      {/* Application Settings Card */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Settings2 className="h-5 w-5" />
                Application Settings
              </CardTitle>
              <CardDescription>
                Configure automated features and scheduling
              </CardDescription>
            </div>
            {localSettings?.updated_by_username && (
              <p className="text-xs text-muted-foreground">
                Last updated by {localSettings.updated_by_username}
              </p>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {settingsLoading ? (
            <div className="flex items-center gap-2">
              <LoadingSpinner size="sm" />
              <span className="text-sm text-muted-foreground">Loading settings...</span>
            </div>
          ) : localSettings ? (
            <div className="space-y-6">
              {/* Domain Discovery Settings */}
              <div className="space-y-4">
                <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
                  Domain Discovery
                </h3>
                <div className="space-y-4 border-l-2 border-muted pl-4">
                  <label className="flex items-start gap-3 cursor-pointer group">
                    <input
                      type="checkbox"
                      checked={localSettings.domain_discovery_auto_refresh}
                      onChange={(e) =>
                        setLocalSettings({
                          ...localSettings,
                          domain_discovery_auto_refresh: e.target.checked,
                        })
                      }
                      className="mt-1 h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
                    />
                    <div className="flex-1">
                      <span className="font-medium group-hover:text-primary transition-colors">
                        Auto-refresh domains
                      </span>
                      <p className="text-sm text-muted-foreground mt-0.5">
                        Automatically update organization domains from Microsoft 365 before each trace pull
                      </p>
                    </div>
                  </label>

                  <div className="space-y-2">
                    <label className="block">
                      <span className="text-sm font-medium">Refresh Interval</span>
                      <div className="flex items-center gap-3 mt-1.5">
                        <input
                          type="number"
                          min="1"
                          max="168"
                          value={localSettings.domain_discovery_refresh_hours}
                          onChange={(e) => {
                            const value = Math.min(168, Math.max(1, parseInt(e.target.value) || 1))
                            setLocalSettings({
                              ...localSettings,
                              domain_discovery_refresh_hours: value,
                            })
                          }}
                          className="w-24 rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                          disabled={!localSettings.domain_discovery_auto_refresh}
                        />
                        <span className="text-sm text-muted-foreground">
                          hours (1-168)
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground mt-1.5">
                        How often to check for new domains. Default: 24 hours.
                      </p>
                    </label>
                  </div>
                </div>
              </div>

              {/* Scheduled Pull Settings */}
              <div className="space-y-4">
                <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
                  Scheduled Pulls
                </h3>
                <div className="space-y-4 border-l-2 border-muted pl-4">
                  <label className="flex items-start gap-3 cursor-pointer group">
                    <input
                      type="checkbox"
                      checked={localSettings.scheduled_pull_enabled}
                      onChange={(e) =>
                        setLocalSettings({
                          ...localSettings,
                          scheduled_pull_enabled: e.target.checked,
                        })
                      }
                      className="mt-1 h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
                    />
                    <div className="flex-1">
                      <span className="font-medium group-hover:text-primary transition-colors">
                        Enable scheduled pulls
                      </span>
                      <p className="text-sm text-muted-foreground mt-0.5">
                        Automatically pull message traces at a scheduled time each day
                      </p>
                    </div>
                  </label>

                  <div className="space-y-2">
                    <label className="block">
                      <span className="text-sm font-medium">Pull Schedule (UTC)</span>
                      <div className="flex items-center gap-3 mt-1.5">
                        <input
                          type="number"
                          min="0"
                          max="23"
                          value={localSettings.scheduled_pull_hour}
                          onChange={(e) => {
                            const value = Math.min(23, Math.max(0, parseInt(e.target.value) || 0))
                            setLocalSettings({
                              ...localSettings,
                              scheduled_pull_hour: value,
                            })
                          }}
                          className="w-20 rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 text-center"
                          disabled={!localSettings.scheduled_pull_enabled}
                        />
                        <span className="text-muted-foreground">:</span>
                        <input
                          type="number"
                          min="0"
                          max="59"
                          value={localSettings.scheduled_pull_minute}
                          onChange={(e) => {
                            const value = Math.min(59, Math.max(0, parseInt(e.target.value) || 0))
                            setLocalSettings({
                              ...localSettings,
                              scheduled_pull_minute: value,
                            })
                          }}
                          className="w-20 rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 text-center"
                          disabled={!localSettings.scheduled_pull_enabled}
                        />
                        <span className="text-sm text-muted-foreground font-mono">
                          {String(localSettings.scheduled_pull_hour).padStart(2, '0')}:
                          {String(localSettings.scheduled_pull_minute).padStart(2, '0')} UTC
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground mt-1.5">
                        Time of day to run automated pulls (in UTC timezone)
                      </p>
                    </label>
                  </div>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center justify-between pt-4 border-t">
                <div className="text-sm text-muted-foreground">
                  {hasChanges && (
                    <span className="text-amber-600 dark:text-amber-400">
                      • Unsaved changes
                    </span>
                  )}
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    onClick={handleResetSettings}
                    disabled={!hasChanges || updateSettings.isPending}
                  >
                    <X className="h-4 w-4 mr-2" />
                    Reset
                  </Button>
                  <Button
                    onClick={handleSaveSettings}
                    disabled={!hasChanges || updateSettings.isPending}
                  >
                    {updateSettings.isPending ? (
                      <>
                        <LoadingSpinner size="sm" className="mr-2" />
                        Saving...
                      </>
                    ) : (
                      <>
                        <Save className="h-4 w-4 mr-2" />
                        Save Settings
                      </>
                    )}
                  </Button>
                </div>
              </div>
            </div>
          ) : (
            <div className="text-center py-8">
              <AlertCircle className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
              <p className="text-muted-foreground">
                Failed to load application settings. You may not have admin permissions.
              </p>
            </div>
          )}
        </CardContent>
      </Card>

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
