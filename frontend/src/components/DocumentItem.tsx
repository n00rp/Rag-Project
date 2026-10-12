import { useState } from 'react'
import { FileText, RotateCw, Trash2 } from 'lucide-react'
import { useDeleteDocument, useRetryDocument } from '../hooks/queries'
import { useToast } from '../hooks/toast'
import { ApiError } from '../lib/api'
import { formatBytes, pluralize } from '../lib/format'
import type { DocumentDto, ViewerTarget } from '../lib/types'
import { StatusBadge } from './StatusBadge'

interface Props {
  doc: DocumentDto
  onOpen: (target: ViewerTarget) => void
}

export function DocumentItem({ doc, onOpen }: Props) {
  const [confirming, setConfirming] = useState(false)
  const remove = useDeleteDocument()
  const retry = useRetryDocument()
  const toast = useToast()

  const meta = [
    doc.pageCount != null ? pluralize(doc.pageCount, 'sida', 'sidor') : null,
    formatBytes(doc.sizeBytes),
  ]
    .filter(Boolean)
    .join(' · ')

  async function confirmDelete() {
    try {
      await remove.mutateAsync(doc.id)
    } catch (e) {
      setConfirming(false)
      toast('error', e instanceof ApiError ? e.message : 'Kunde inte ta bort dokumentet.')
    }
  }

  return (
    <li className="rounded-xl border border-line bg-surface p-3">
      <div className="flex items-start gap-3">
        <FileText className="mt-0.5 size-5 shrink-0 text-muted" aria-hidden />
        <div className="min-w-0 flex-1">
          <button
            type="button"
            title={doc.fileName}
            onClick={() => onOpen({ documentId: doc.id, fileName: doc.fileName, page: 1 })}
            className="block w-full truncate text-left text-sm font-medium hover:text-accent hover:underline"
          >
            {doc.fileName}
          </button>
          <div className="mt-0.5 text-xs text-muted">{meta}</div>
          <div className="mt-2 flex items-center justify-between gap-2">
            <StatusBadge status={doc.status} />
            {confirming ? (
              <span className="flex items-center gap-1 text-xs">
                <button
                  onClick={confirmDelete}
                  disabled={remove.isPending}
                  className="rounded-md bg-danger px-2 py-1 font-medium text-white disabled:opacity-60"
                >
                  Ta bort
                </button>
                <button
                  onClick={() => setConfirming(false)}
                  className="rounded-md px-2 py-1 text-muted hover:bg-surface-2"
                >
                  Avbryt
                </button>
              </span>
            ) : (
              <button
                onClick={() => setConfirming(true)}
                aria-label={`Ta bort ${doc.fileName}`}
                className="-m-1 rounded-md p-1.5 text-muted hover:bg-danger-soft hover:text-danger"
              >
                <Trash2 className="size-4" />
              </button>
            )}
          </div>
        </div>
      </div>

      {doc.status === 'Failed' && (
        <div className="mt-3 rounded-lg bg-danger-soft p-2.5 text-xs text-danger">
          <p>{doc.error ?? 'Bearbetningen misslyckades.'}</p>
          <button
            onClick={() => retry.mutate(doc.id)}
            disabled={retry.isPending}
            className="mt-1.5 inline-flex items-center gap-1 font-medium underline-offset-2 hover:underline disabled:opacity-60"
          >
            <RotateCw className="size-3" aria-hidden /> Försök igen
          </button>
        </div>
      )}
    </li>
  )
}
