import { useState } from 'react'
import { ChevronLeft, ChevronRight, ExternalLink } from 'lucide-react'
import { documentFileUrl } from '../lib/api'
import type { ViewerTarget } from '../lib/types'
import { PdfPage } from './PdfPage'
import { Sheet } from './ui/Sheet'

interface Props {
  target: ViewerTarget | null
  onClose: () => void
}

/**
 * Shows the cited page with the cited excerpt highlighted. If pdf.js cannot render the file, it falls
 * back to the browser's built-in viewer (#page=N), which cannot highlight but always works.
 */
export function PdfViewer({ target, onClose }: Props) {
  return (
    <Sheet
      open={target !== null}
      onClose={onClose}
      side="right"
      title={target ? `${target.fileName} · sida ${target.page}` : ''}
      widthClass="w-[min(48rem,100vw)]"
    >
      {/* Re-key so a new source starts on its own page with fresh state. */}
      {target && <ViewerBody key={`${target.documentId}-${target.page}-${target.snippet}`} target={target} />}
    </Sheet>
  )
}

function ViewerBody({ target }: { target: ViewerTarget }) {
  const [page, setPage] = useState(target.page)
  const [pageCount, setPageCount] = useState<number | null>(null)
  const [failed, setFailed] = useState(false)

  const url = documentFileUrl(target.documentId)
  // navpanes=0 hides the thumbnail sidebar so the page itself gets the room.
  const browserSrc = `${url}#page=${page}&navpanes=0`

  return (
    <div className="flex h-full flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden bg-surface-2 p-3 [scrollbar-gutter:stable]">
        {failed ? (
          <iframe src={browserSrc} title={`${target.fileName}, sida ${page}`} className="h-full w-full" />
        ) : (
          <PdfPage
            url={url}
            page={page}
            snippet={page === target.page ? target.snippet : undefined}
            onPageCount={setPageCount}
            onError={() => setFailed(true)}
          />
        )}
      </div>
      <div className="flex items-center justify-between gap-2 border-t border-line px-3 py-2 text-xs text-muted">
        <div className="flex items-center gap-1">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={failed || page <= 1}
            aria-label="Föregående sida"
            className="rounded-lg p-1.5 hover:bg-surface-2 hover:text-fg disabled:opacity-40"
          >
            <ChevronLeft className="size-4" />
          </button>
          <span aria-live="polite">
            Sida {page}
            {pageCount ? ` av ${pageCount}` : ''}
          </span>
          <button
            onClick={() => setPage((p) => (pageCount ? Math.min(pageCount, p + 1) : p + 1))}
            disabled={failed || (pageCount !== null && page >= pageCount)}
            aria-label="Nästa sida"
            className="rounded-lg p-1.5 hover:bg-surface-2 hover:text-fg disabled:opacity-40"
          >
            <ChevronRight className="size-4" />
          </button>
        </div>
        <a
          href={browserSrc}
          target="_blank"
          rel="noreferrer"
          className="flex items-center gap-1.5 font-medium hover:text-accent"
        >
          <ExternalLink className="size-3.5" aria-hidden /> Öppna i ny flik
        </a>
      </div>
    </div>
  )
}
