import { useId, useState } from 'react'
import { FileText } from 'lucide-react'
import type { ChatSource, ViewerTarget } from '../lib/types'

interface Props {
  index: number
  source: ChatSource
  onOpen: (target: ViewerTarget) => void
}

const CARD_WIDTH = 288
const MARGIN = 8

/** A numbered citation inside the answer. Hover or focus shows where it comes from; click opens the page. */
export function CitationChip({ index, source, onOpen }: Props) {
  const id = useId()
  const [card, setCard] = useState<{ left: number; top: number; above: boolean } | null>(null)

  function show(el: HTMLElement) {
    const rect = el.getBoundingClientRect()
    const left = Math.min(Math.max(rect.left + rect.width / 2 - CARD_WIDTH / 2, MARGIN), window.innerWidth - CARD_WIDTH - MARGIN)
    const above = rect.top > 170 // otherwise there is no room above: put it below
    setCard({ left, top: above ? rect.top - MARGIN : rect.bottom + MARGIN, above })
  }

  return (
    <span className="relative inline-block">
      <button
        type="button"
        onClick={() => onOpen({ documentId: source.documentId, fileName: source.fileName, page: source.page, snippet: source.snippet })}
        onMouseEnter={(e) => show(e.currentTarget)}
        onMouseLeave={() => setCard(null)}
        onFocus={(e) => show(e.currentTarget)}
        onBlur={() => setCard(null)}
        aria-describedby={card ? id : undefined}
        aria-label={`Källa ${index}: ${source.fileName}, sida ${source.page}`}
        className="mx-0.5 inline-flex h-5 min-w-5 -translate-y-px items-center justify-center rounded-md bg-accent-soft px-1 align-middle text-xs font-semibold text-accent transition-colors duration-[var(--dur-fast)] hover:bg-accent hover:text-accent-fg"
      >
        {index}
      </button>
      {card && (
        <span
          id={id}
          role="tooltip"
          style={{ left: card.left, top: card.top, width: CARD_WIDTH, transform: card.above ? 'translateY(-100%)' : undefined }}
          className="animate-fade pointer-events-none fixed z-50 block rounded-xl border border-line bg-surface p-3 text-left text-sm font-normal leading-snug shadow-lift"
        >
          <span className="flex items-center gap-1.5 text-xs font-medium">
            <FileText className="size-3.5 shrink-0 text-muted" aria-hidden />
            <span className="truncate">{source.fileName}</span>
            <span className="shrink-0 text-muted">· sida {source.page}</span>
          </span>
          <span className="mt-1.5 line-clamp-4 block text-xs leading-relaxed text-muted">{source.snippet}</span>
          <span className="mt-2 block text-xs font-medium text-accent">Klicka för att öppna sidan</span>
        </span>
      )}
    </span>
  )
}
