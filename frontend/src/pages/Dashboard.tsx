import { Link } from 'react-router-dom'
import {
  Mail,
  CheckCircle,
  XCircle,
  Clock,
  ArrowDownRight,
  ArrowUpRight,
  ArrowLeftRight,
  RefreshCw,
} from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { useDashboard } from '@/hooks/useDashboard'
import { LoadingPage } from '@/components/LoadingSpinner'
import { StatusBadge } from '@/components/StatusBadge'
import { formatDate } from '@/lib/utils'

export function Dashboard() {
  const { data, isLoading, error, refetch } = useDashboard()

  if (isLoading) return <LoadingPage />

  if (error) {
    return (
      <div className="text-center py-12">
        <p className="text-destructive mb-4">Failed to load dashboard data</p>
        <Button onClick={() => refetch()}>Retry</Button>
      </div>
    )
  }

  if (!data) return null

  const stats = [
    {
      title: 'Total Traces',
      value: data.total_traces.toLocaleString(),
      icon: Mail,
      description: 'All time',
    },
    {
      title: 'Today',
      value: data.traces_today.toLocaleString(),
      icon: Clock,
      description: 'Messages today',
    },
    {
      title: 'This Week',
      value: data.traces_this_week.toLocaleString(),
      icon: RefreshCw,
      description: 'Last 7 days',
    },
  ]

  const statusStats = [
    { label: 'Delivered', value: data.delivered_count, icon: CheckCircle, color: 'text-green-500', filter: 'Delivered' },
    { label: 'Failed', value: data.failed_count, icon: XCircle, color: 'text-red-500', filter: 'Failed' },
    { label: 'Pending', value: data.pending_count, icon: Clock, color: 'text-yellow-500', filter: 'Pending' },
    { label: 'Quarantined', value: data.quarantined_count, icon: XCircle, color: 'text-purple-500', filter: 'Quarantined' },
  ]

  const directionStats = [
    { label: 'Inbound', value: data.inbound_count, icon: ArrowDownRight, color: 'text-blue-500', filter: 'Inbound' },
    { label: 'Outbound', value: data.outbound_count, icon: ArrowUpRight, color: 'text-green-500', filter: 'Outbound' },
    { label: 'Internal', value: data.internal_count, icon: ArrowLeftRight, color: 'text-gray-500', filter: 'Internal' },
  ]

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Dashboard</h1>
        <Button variant="outline" onClick={() => refetch()}>
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Main Stats */}
      <div className="grid gap-4 md:grid-cols-3">
        {stats.map((stat) => (
          <Card key={stat.title}>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                {stat.title}
              </CardTitle>
              <stat.icon className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stat.value}</div>
              <p className="text-xs text-muted-foreground">{stat.description}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Status and Direction Breakdown */}
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Status Breakdown</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {statusStats.map((stat) => (
                <Link
                  key={stat.label}
                  to={`/traces?status=${stat.filter}`}
                  className="flex items-center justify-between p-2 rounded-md hover:bg-muted transition-colors cursor-pointer"
                >
                  <div className="flex items-center gap-2">
                    <stat.icon className={`h-4 w-4 ${stat.color}`} />
                    <span className="text-sm">{stat.label}</span>
                  </div>
                  <span className="font-semibold">{stat.value.toLocaleString()}</span>
                </Link>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Direction Breakdown</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {directionStats.map((stat) => (
                <Link
                  key={stat.label}
                  to={`/traces?direction=${stat.filter}`}
                  className="flex items-center justify-between p-2 rounded-md hover:bg-muted transition-colors cursor-pointer"
                >
                  <div className="flex items-center gap-2">
                    <stat.icon className={`h-4 w-4 ${stat.color}`} />
                    <span className="text-sm">{stat.label}</span>
                  </div>
                  <span className="font-semibold">{stat.value.toLocaleString()}</span>
                </Link>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Last Pull Info */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Last Pull</CardTitle>
          <Link to="/pull-history">
            <Button variant="link" className="text-sm">
              View all history
            </Button>
          </Link>
        </CardHeader>
        <CardContent>
          {data.last_pull ? (
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">{formatDate(data.last_pull.start_time)}</p>
                <p className="text-sm text-muted-foreground">
                  {data.last_pull.records_pulled.toLocaleString()} records pulled
                  ({data.last_pull.records_new} new)
                </p>
              </div>
              <StatusBadge status={data.last_pull.status} />
            </div>
          ) : (
            <p className="text-muted-foreground">No pull history yet</p>
          )}
        </CardContent>
      </Card>

      {/* Recent Pulls */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Recent Activity</CardTitle>
          <Link to="/traces">
            <Button variant="link" className="text-sm">
              View all traces
            </Button>
          </Link>
        </CardHeader>
        <CardContent>
          {data.recent_pulls.length > 0 ? (
            <div className="space-y-3">
              {data.recent_pulls.slice(0, 5).map((pull) => (
                <div
                  key={pull.id}
                  className="flex items-center justify-between py-2 border-b last:border-0"
                >
                  <div className="flex items-center gap-3">
                    <StatusBadge status={pull.status} />
                    <div>
                      <p className="text-sm font-medium">
                        {pull.trigger_type} pull
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {formatDate(pull.start_time)}
                      </p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-medium">
                      {pull.records_pulled.toLocaleString()} records
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {pull.duration_formatted || '-'}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-muted-foreground">No recent activity</p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
