import { useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { usePullHistory } from '@/hooks/usePullHistory'
import { LoadingPage } from '@/components/LoadingSpinner'
import { Pagination } from '@/components/Pagination'
import { StatusBadge } from '@/components/StatusBadge'
import { formatDate } from '@/lib/utils'

const PAGE_SIZE = 25

export function PullHistoryPage() {
  const [page, setPage] = useState(1)
  const { data, isLoading, error, refetch } = usePullHistory({ page })

  const totalPages = data ? Math.ceil(data.count / PAGE_SIZE) : 0

  if (isLoading && !data) return <LoadingPage />

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Pull History</h1>
        <Button variant="outline" onClick={() => refetch()}>
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      <Card>
        <CardContent className="p-0">
          {error ? (
            <div className="text-center py-12">
              <p className="text-destructive mb-4">Failed to load pull history</p>
              <Button onClick={() => refetch()}>Retry</Button>
            </div>
          ) : data && data.results.length > 0 ? (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Start Time</TableHead>
                    <TableHead>Date Range</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Records</TableHead>
                    <TableHead>New</TableHead>
                    <TableHead>Duration</TableHead>
                    <TableHead>Triggered By</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.results.map((pull) => (
                    <TableRow key={pull.id}>
                      <TableCell className="whitespace-nowrap">
                        {formatDate(pull.start_time)}
                      </TableCell>
                      <TableCell className="whitespace-nowrap text-sm">
                        {new Date(pull.pull_start_date).toLocaleDateString()} -{' '}
                        {new Date(pull.pull_end_date).toLocaleDateString()}
                      </TableCell>
                      <TableCell>
                        <StatusBadge status={pull.status} />
                      </TableCell>
                      <TableCell>{pull.trigger_type}</TableCell>
                      <TableCell>{pull.records_pulled.toLocaleString()}</TableCell>
                      <TableCell>{pull.records_new.toLocaleString()}</TableCell>
                      <TableCell>{pull.duration_formatted || '-'}</TableCell>
                      <TableCell>{pull.triggered_by || 'system'}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              <Pagination
                currentPage={page}
                totalPages={totalPages}
                totalItems={data.count}
                pageSize={PAGE_SIZE}
                onPageChange={setPage}
              />
            </>
          ) : (
            <div className="text-center py-12 text-muted-foreground">
              No pull history found
            </div>
          )}
        </CardContent>
      </Card>

      {/* Failed Pulls Detail */}
      {data?.results.some((p) => p.status === 'Failed' && p.error_message) && (
        <Card>
          <CardHeader>
            <CardTitle>Recent Errors</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {data.results
              .filter((p) => p.status === 'Failed' && p.error_message)
              .slice(0, 3)
              .map((pull) => (
                <div key={pull.id} className="p-4 bg-destructive/10 rounded-lg">
                  <p className="text-sm font-medium text-destructive">
                    {formatDate(pull.start_time)}
                  </p>
                  <p className="text-sm mt-1">{pull.error_message}</p>
                </div>
              ))}
          </CardContent>
        </Card>
      )}
    </div>
  )
}
