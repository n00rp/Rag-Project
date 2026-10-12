import { useDocuments } from '../hooks/queries'
import type { ViewerTarget } from '../lib/types'
import { DocumentItem } from './DocumentItem'
import { UploadDropzone } from './UploadDropzone'

export function DocumentPanel({ onOpen }: { onOpen: (target: ViewerTarget) => void }) {
  const { data: docs, isPending, isError } = useDocuments()

  return (
    <div className="flex h-full flex-col gap-4 p-4">
      <UploadDropzone />

      <div className="flex items-baseline justify-between">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-muted">Dokument</h2>
        {docs && <span className="text-xs text-muted">{docs.length}</span>}
      </div>

      <div className="-mr-2 min-h-0 flex-1 overflow-y-auto pr-2">
        {isPending && (
          <div className="space-y-2" aria-label="Laddar dokument">
            {[0, 1, 2].map((i) => (
              <div key={i} className="h-[88px] animate-pulse rounded-xl bg-surface-2" />
            ))}
          </div>
        )}
        {isError && (
          <p className="rounded-xl bg-danger-soft p-3 text-sm text-danger">
            Kunde inte hämta dokumenten. Försöker igen…
          </p>
        )}
        {docs && docs.length === 0 && (
          <p className="px-1 py-6 text-center text-sm text-muted">
            Inga dokument ännu. Ladda upp ett protokoll eller beslutsunderlag för att komma igång.
          </p>
        )}
        {docs && docs.length > 0 && (
          <ul className="space-y-2">
            {docs.map((d) => (
              <DocumentItem key={d.id} doc={d} onOpen={onOpen} />
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
