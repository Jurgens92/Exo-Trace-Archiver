import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Search, Filter, X } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useTraces } from '@/hooks/useTraces'
import { LoadingPage } from '@/components/LoadingSpinner'
import { Pagination } from '@/components/Pagination'
import { StatusBadge, DirectionBadge } from '@/components/StatusBadge'
import { formatDateShort } from '@/lib/utils'
import type { TraceFilterParams, TraceStatus, TraceDirection } from '@/api/types'

const PAGE_SIZE = 50

export function TracesPage() {
  const [filters, setFilters] = useState<TraceFilterParams>({
    page: 1,
    page_size: PAGE_SIZE,
  })
  const [showFilters, setShowFilters] = useState(false)
  const [searchInput, setSearchInput] = useState('')

  const { data, isLoading, error, refetch } = useTraces(filters)

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    setFilters((prev) => ({ ...prev, search: searchInput, page: 1 }))
  }

  const handleFilterChange = (key: keyof TraceFilterParams, value: string) => {
    if (value === 'all') {
      const newFilters = { ...filters }
      delete newFilters[key]
      newFilters.page = 1
      setFilters(newFilters)
    } else {
      setFilters((prev) => ({ ...prev, [key]: value, page: 1 }))
    }
  }

  const clearFilters = () => {
    setFilters({ page: 1, page_size: PAGE_SIZE })
    setSearchInput('')
  }

  const totalPages = data ? Math.ceil(data.count / PAGE_SIZE) : 0

  if (isLoading && !data) return <LoadingPage />

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Message Traces</h1>
        <Button
          variant="outline"
          onClick={() => setShowFilters(!showFilters)}
        >
          <Filter className="h-4 w-4 mr-2" />
          Filters
        </Button>
      </div>

      {/* Search Bar */}
      <Card>
        <CardContent className="pt-6">
          <form onSubmit={handleSearch} className="flex gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search by sender, recipient, subject, or message ID..."
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                className="pl-10"
              />
            </div>
            <Button type="submit">Search</Button>
          </form>
        </CardContent>
      </Card>

      {/* Filters */}
      {showFilters && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between py-4">
            <CardTitle className="text-lg">Filters</CardTitle>
            <Button variant="ghost" size="sm" onClick={clearFilters}>
              <X className="h-4 w-4 mr-1" />
              Clear all
            </Button>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 md:grid-cols-4">
              <div className="space-y-2">
                <Label>Status</Label>
                <Select
                  value={filters.status || 'all'}
                  onValueChange={(value) => handleFilterChange('status', value)}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="All statuses" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All statuses</SelectItem>
                    <SelectItem value="Delivered">Delivered</SelectItem>
                    <SelectItem value="Failed">Failed</SelectItem>
                    <SelectItem value="Pending">Pending</SelectItem>
                    <SelectItem value="Quarantined">Quarantined</SelectItem>
                    <SelectItem value="FilteredAsSpam">Filtered as Spam</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>Direction</Label>
                <Select
                  value={filters.direction || 'all'}
                  onValueChange={(value) => handleFilterChange('direction', value)}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="All directions" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All directions</SelectItem>
                    <SelectItem value="Inbound">Inbound</SelectItem>
                    <SelectItem value="Outbound">Outbound</SelectItem>
                    <SelectItem value="Internal">Internal</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>Start Date</Label>
                <Input
                  type="date"
                  value={filters.start_date?.split('T')[0] || ''}
                  onChange={(e) =>
                    handleFilterChange(
                      'start_date',
                      e.target.value ? `${e.target.value}T00:00:00Z` : 'all'
                    )
                  }
                />
              </div>

              <div className="space-y-2">
                <Label>End Date</Label>
                <Input
                  type="date"
                  value={filters.end_date?.split('T')[0] || ''}
                  onChange={(e) =>
                    handleFilterChange(
                      'end_date',
                      e.target.value ? `${e.target.value}T23:59:59Z` : 'all'
                    )
                  }
                />
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Results Table */}
      <Card>
        <CardContent className="p-0">
          {error ? (
            <div className="text-center py-12">
              <p className="text-destructive mb-4">Failed to load traces</p>
              <Button onClick={() => refetch()}>Retry</Button>
            </div>
          ) : data && data.results.length > 0 ? (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Date</TableHead>
                    <TableHead>Sender</TableHead>
                    <TableHead>Recipient</TableHead>
                    <TableHead>Subject</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Direction</TableHead>
                    <TableHead>Size</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.results.map((trace) => (
                    <TableRow key={trace.id}>
                      <TableCell className="whitespace-nowrap">
                        <Link
                          to={`/traces/${trace.id}`}
                          className="text-primary hover:underline"
                        >
                          {formatDateShort(trace.received_date)}
                        </Link>
                      </TableCell>
                      <TableCell className="max-w-[200px] truncate">
                        {trace.sender}
                      </TableCell>
                      <TableCell className="max-w-[200px] truncate">
                        {trace.recipient}
                      </TableCell>
                      <TableCell className="max-w-[300px] truncate">
                        <Link
                          to={`/traces/${trace.id}`}
                          className="hover:underline"
                        >
                          {trace.subject || '(no subject)'}
                        </Link>
                      </TableCell>
                      <TableCell>
                        <StatusBadge status={trace.status} />
                      </TableCell>
                      <TableCell>
                        <DirectionBadge direction={trace.direction} />
                      </TableCell>
                      <TableCell>{trace.size_formatted}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              <Pagination
                currentPage={filters.page || 1}
                totalPages={totalPages}
                totalItems={data.count}
                pageSize={PAGE_SIZE}
                onPageChange={(page) => setFilters((prev) => ({ ...prev, page }))}
              />
            </>
          ) : (
            <div className="text-center py-12 text-muted-foreground">
              No message traces found
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
