import { useId } from 'react'
import { ChevronDown } from 'lucide-react'
import type { ChatSource, ViewerTarget } from '../lib/types'
import { SourceCard } from './SourceCard'

interface Props {
  sources: ChatSource[]
  onOpen: (target: ViewerTarget) => void
}

function short(name: string, max = 26): string {
  const base = name.replace(/\.pdf$/i, '')
  return base.length > max ? `${base.slice(0, max - 1)}…` : base
}

/** The sources of an answer as a quiet row of chips; the excerpts are one click away. */
export function SourceStrip({ sources, onOpen }: Props) {
  const labelId = useId()
  if (sources.length === 0) return null

  return (
    <div className="mt-4">
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="mr-1 text-xs font-medium text-muted" id={labelId}>Källor</span>
        <ul className="contents" aria-labelledby={labelId}>
          {sources.map((s, i) => (
            <li key={`${s.documentId}-${s.page}-${i}`} className="contents">
              <button
                type="button"
                onClick={() => onOpen({ documentId: s.documentId, fileName: s.fileName, page: s.page, snippet: s.snippet })}
                title={`${s.fileName}, sida ${s.page}`}
                className="group inline-flex items-center gap-1.5 rounded-full border border-line bg-surface py-0.5 pl-0.5 pr-2.5 text-xs shadow-soft transition-colors duration-[var(--dur-fast)] hover:border-accent/60 hover:bg-accent-soft/50"
              >
                <span className="flex size-5 items-center justify-center rounded-full bg-accent-soft text-[0.7rem] font-semibold text-accent">
                  {i + 1}
                </span>
                <span className="max-w-40 truncate">{short(s.fileName)}</span>
                <span className="text-muted">s. {s.page}</span>
              </button>
            </li>
          ))}
        </ul>
      </div>

      <details className="group mt-2">
        <summary className="flex w-fit cursor-pointer list-none items-center gap-1 rounded-md text-xs font-medium text-muted hover:text-fg">
          <ChevronDown className="size-3.5 transition-transform group-open:rotate-180" aria-hidden />
          Visa utdrag
        </summary>
        <div className="mt-2 space-y-2">
          {sources.map((s, i) => (
            <SourceCard key={`${s.documentId}-${s.page}-${i}`} index={i + 1} source={s} onOpen={onOpen} />
          ))}
        </div>
      </details>
    </div>
  )
}
