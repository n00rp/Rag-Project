import { AlertTriangle, CheckCircle2, Clock, Loader2 } from 'lucide-react'
import { clsx } from 'clsx'
import type { DocumentStatus } from '../lib/types'

const CONFIG: Record<DocumentStatus, { label: string; className: string; icon: typeof Clock }> = {
  Queued: { label: 'I kö', className: 'bg-surface-2 text-muted', icon: Clock },
  Processing: { label: 'Bearbetas', className: 'bg-accent-soft text-accent', icon: Loader2 },
  Ready: { label: 'Klar', className: 'bg-ok-soft text-ok', icon: CheckCircle2 },
  Failed: { label: 'Misslyckades', className: 'bg-danger-soft text-danger', icon: AlertTriangle },
}

export function StatusBadge({ status }: { status: DocumentStatus }) {
  const { label, className, icon: Icon } = CONFIG[status]
  return (
    <span className={clsx('inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium', className)}>
      <Icon className={clsx('size-3', status === 'Processing' && 'animate-spin')} aria-hidden />
      {label}
    </span>
  )
}
