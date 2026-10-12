import { ExternalLink } from 'lucide-react'
import { documentFileUrl } from '../lib/api'
import type { ViewerTarget } from '../lib/types'
import { Sheet } from './ui/Sheet'

interface Props {
  target: ViewerTarget | null
  onClose: () => void
}

/** Opens the original PDF at the cited page using the browser's built-in PDF viewer (#page=N). */
export function PdfViewer({ target, onClose }: Props) {
  // navpanes=0 hides the thumbnail sidebar so the page itself gets the room.
  const src = target ? `${documentFileUrl(target.documentId)}#page=${target.page}&navpanes=0` : ''

  return (
    <Sheet
      open={target !== null}
      onClose={onClose}
      side="right"
      title={target ? `${target.fileName} · sida ${target.page}` : ''}
      widthClass="w-[min(48rem,100vw)]"
    >
      {target && (
        <div className="flex h-full flex-col">
          <iframe
            // Re-key so the viewer jumps to the new page when another source is clicked.
            key={`${target.documentId}-${target.page}`}
            src={src}
            title={`${target.fileName}, sida ${target.page}`}
            className="min-h-0 flex-1 bg-surface-2"
          />
          <a
            href={src}
            target="_blank"
            rel="noreferrer"
            className="flex items-center justify-center gap-1.5 border-t border-line py-2.5 text-xs font-medium text-muted hover:text-accent"
          >
            <ExternalLink className="size-3.5" aria-hidden /> Öppna i ny flik
          </a>
        </div>
      )}
    </Sheet>
  )
}
