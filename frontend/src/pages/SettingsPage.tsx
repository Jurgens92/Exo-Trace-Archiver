import { useState } from 'react'
import { RefreshCw, Play, Check, X, AlertCircle } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { useConfig } from '@/hooks/useDashboard'
import { useManualPull } from '@/hooks/usePullHistory'
import { LoadingPage, LoadingSpinner } from '@/components/LoadingSpinner'
import { useToast } from '@/components/ui/use-toast'

export function SettingsPage() {
  const { data: config, isLoading, error, refetch } = useConfig()
  const manualPull = useManualPull()
  const { toast } = useToast()

  const handleManualPull = async () => {
    try {
      const result = await manualPull.mutateAsync({})
      toast({
        title: 'Pull completed',
        description: `Pulled ${result.records_pulled} records (${result.records_new} new)`,
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
              Pulls yesterday's message traces by default
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Microsoft 365 Configuration */}
      <Card>
        <CardHeader>
          <CardTitle>Microsoft 365 Configuration</CardTitle>
          <CardDescription>
            Azure AD app registration and authentication settings
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <ConfigItem
              label="Tenant ID"
              value={config.legacy_microsoft365?.tenant_id ?? 'Not configured'}
            />
            <ConfigItem
              label="Client ID"
              value={config.legacy_microsoft365?.client_id ?? 'Not configured'}
            />
            <ConfigItem
              label="Auth Method"
              value={config.legacy_microsoft365?.auth_method ?? 'Not configured'}
            />
            <ConfigItem
              label="API Method"
              value={config.legacy_microsoft365?.api_method ?? 'Not configured'}
            />
            <ConfigItem
              label="Organization"
              value={config.legacy_microsoft365?.organization ?? 'Not configured'}
            />
            <ConfigItem
              label="Certificate"
              value={config.legacy_microsoft365?.certificate_configured ?? false}
              type="boolean"
            />
          </div>
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
}

function ConfigItem({ label, value, type = 'text' }: ConfigItemProps) {
  return (
    <div className="space-y-1">
      <p className="text-sm font-medium text-muted-foreground">{label}</p>
      {type === 'boolean' ? (
        <div className="flex items-center gap-2">
          {value ? (
            <>
              <Check className="h-4 w-4 text-green-500" />
              <span>Configured</span>
            </>
          ) : (
            <>
              <X className="h-4 w-4 text-muted-foreground" />
              <span className="text-muted-foreground">Not configured</span>
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
