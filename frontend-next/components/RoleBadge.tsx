'use client'

import { Badge } from '@/components/ui/badge'
import { ROLE_COLORS, ROLE_LABELS } from '@/lib/constants'
import { cn } from '@/lib/utils'

interface RoleBadgeProps {
  role: string
  className?: string
}

export function RoleBadge({ role, className }: RoleBadgeProps) {
  const colorClass = ROLE_COLORS[role] ?? 'bg-neutral-500'
  const label = ROLE_LABELS[role] ?? role

  return (
    <Badge
      className={cn(
        colorClass,
        'text-white border-0 text-xs font-medium select-none',
        className,
      )}
    >
      {label}
    </Badge>
  )
}
