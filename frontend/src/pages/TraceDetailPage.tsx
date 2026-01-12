import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, Copy, Check } from 'lucide-react'
import { useState } from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { useTrace } from '@/hooks/useTraces'
import { LoadingPage } from '@/components/LoadingSpinner'
import { StatusBadge, DirectionBadge } from '@/components/StatusBadge'
import { formatDate } from '@/lib/utils'

export function TraceDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { data: trace, isLoading, error } = useTrace(Number(id))
  const [copied, setCopied] = useState(false)

  const copyMessageId = () => {
    if (trace?.message_id) {
      navigator.clipboard.writeText(trace.message_id)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  if (isLoading) return <LoadingPage />

  if (error || !trace) {
    return (
      <div className="space-y-6">
        <Link to="/traces">
          <Button variant="ghost">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to traces
          </Button>
        </Link>
        <div className="text-center py-12">
          <p className="text-destructive">Failed to load trace details</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link to="/traces">
          <Button variant="ghost" size="sm">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back
          </Button>
        </Link>
        <h1 className="text-2xl font-bold">Message Trace Detail</h1>
      </div>

      {/* Overview Card */}
      <Card>
        <CardHeader>
          <CardTitle>Overview</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <p className="text-sm font-medium text-muted-foreground">Subject</p>
              <p className="text-lg font-semibold">{trace.subject || '(no subject)'}</p>
            </div>
            <div className="flex gap-4">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Status</p>
                <StatusBadge status={trace.status} />
              </div>
              <div>
                <p className="text-sm font-medium text-muted-foreground">Direction</p>
                <DirectionBadge direction={trace.direction} />
              </div>
            </div>
          </div>

          <Separator />

          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <p className="text-sm font-medium text-muted-foreground">From</p>
              <p className="font-mono text-sm">{trace.sender}</p>
            </div>
            <div>
              <p className="text-sm font-medium text-muted-foreground">To</p>
              <p className="font-mono text-sm">{trace.recipient}</p>
            </div>
          </div>

          <Separator />

          <div className="grid gap-4 md:grid-cols-3">
            <div>
              <p className="text-sm font-medium text-muted-foreground">Received</p>
              <p>{formatDate(trace.received_date)}</p>
            </div>
            <div>
              <p className="text-sm font-medium text-muted-foreground">Size</p>
              <p>{trace.size_formatted}</p>
            </div>
            <div>
              <p className="text-sm font-medium text-muted-foreground">Traced</p>
              <p>{formatDate(trace.trace_date)}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Message ID Card */}
      <Card>
        <CardHeader>
          <CardTitle>Message ID</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-2">
            <code className="flex-1 p-3 bg-muted rounded-md text-sm font-mono break-all">
              {trace.message_id}
            </code>
            <Button variant="outline" size="sm" onClick={copyMessageId}>
              {copied ? (
                <Check className="h-4 w-4" />
              ) : (
                <Copy className="h-4 w-4" />
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Event Data Card */}
      {trace.event_data && Object.keys(trace.event_data).length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Event Data</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="p-4 bg-muted rounded-md text-sm overflow-x-auto">
              {JSON.stringify(trace.event_data, null, 2)}
            </pre>
          </CardContent>
        </Card>
      )}

      {/* Raw JSON Card */}
      {trace.raw_json && (
        <Card>
          <CardHeader>
            <CardTitle>Raw API Response</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="p-4 bg-muted rounded-md text-sm overflow-x-auto max-h-96">
              {JSON.stringify(trace.raw_json, null, 2)}
            </pre>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
