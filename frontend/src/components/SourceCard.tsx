import { FileText } from 'lucide-react'
import type { ChatSource, ViewerTarget } from '../lib/types'

interface Props {
  index: number
  source: ChatSource
  onOpen: (target: ViewerTarget) => void
}

export function SourceCard({ index, source, onOpen }: Props) {
  return (
    <button
      type="button"
      onClick={() => onOpen({ documentId: source.documentId, fileName: source.fileName, page: source.page })}
      className="group flex w-full gap-3 rounded-xl border border-line bg-surface p-3 text-left transition-colors hover:border-accent/60"
    >
      <span className="flex size-6 shrink-0 items-center justify-center rounded-md bg-accent-soft text-xs font-semibold text-accent">
        {index}
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex items-center gap-1.5 text-xs font-medium">
          <FileText className="size-3.5 shrink-0 text-muted" aria-hidden />
          <span className="truncate group-hover:text-accent">{source.fileName}</span>
          <span className="shrink-0 text-muted">· sida {source.page}</span>
        </span>
        <span className="mt-1 line-clamp-3 block text-xs leading-relaxed text-muted">{source.snippet}</span>
      </span>
    </button>
  )
}
