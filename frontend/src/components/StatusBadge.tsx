import { Badge } from '@/components/ui/badge'
import type { TraceStatus, TraceDirection, PullStatus } from '@/api/types'

interface StatusBadgeProps {
  status: TraceStatus | PullStatus
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const variants: Record<string, 'default' | 'secondary' | 'destructive' | 'outline' | 'success' | 'warning'> = {
    Delivered: 'success',
    Success: 'success',
    Failed: 'destructive',
    Pending: 'warning',
    Running: 'default',
    Partial: 'warning',
    Expanded: 'secondary',
    Quarantined: 'destructive',
    FilteredAsSpam: 'destructive',
    Cancelled: 'secondary',
    None: 'outline',
    Unknown: 'outline',
  }

  return (
    <Badge variant={variants[status] || 'outline'}>
      {status}
    </Badge>
  )
}

interface DirectionBadgeProps {
  direction: TraceDirection
}

export function DirectionBadge({ direction }: DirectionBadgeProps) {
  const variants: Record<TraceDirection, 'default' | 'secondary' | 'outline'> = {
    Inbound: 'default',
    Outbound: 'secondary',
    Internal: 'outline',
    Unknown: 'outline',
  }

  return (
    <Badge variant={variants[direction]}>
      {direction}
    </Badge>
  )
}
