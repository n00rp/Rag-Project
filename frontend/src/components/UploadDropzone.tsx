import { useRef, useState, type DragEvent } from 'react'
import { UploadCloud } from 'lucide-react'
import { clsx } from 'clsx'
import { useUploadDocument } from '../hooks/queries'
import { useToast } from '../hooks/toast'
import { ApiError } from '../lib/api'
import { MAX_UPLOAD_BYTES, formatBytes } from '../lib/format'

/** Returns a user-facing reason if the file can't be uploaded, otherwise null. */
export function validateFile(file: File): string | null {
  const isPdf = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')
  if (!isPdf) return `${file.name} är inte en PDF-fil.`
  if (file.size > MAX_UPLOAD_BYTES) return `${file.name} är för stor (max ${formatBytes(MAX_UPLOAD_BYTES)}).`
  return null
}

export function UploadDropzone() {
  const input = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const upload = useUploadDocument()
  const toast = useToast()

  async function handleFiles(files: FileList | File[]) {
    for (const file of Array.from(files)) {
      const problem = validateFile(file)
      if (problem) {
        toast('error', problem)
        continue
      }
      try {
        await upload.mutateAsync(file)
      } catch (e) {
        toast('error', e instanceof ApiError ? e.message : `Kunde inte ladda upp ${file.name}.`)
      }
    }
  }

  function onDrop(e: DragEvent) {
    e.preventDefault()
    setDragging(false)
    void handleFiles(e.dataTransfer.files)
  }

  return (
    <button
      type="button"
      onClick={() => input.current?.click()}
      onDragOver={(e) => {
        e.preventDefault()
        setDragging(true)
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
      className={clsx(
        'group flex w-full flex-col items-center gap-1.5 rounded-xl border-2 border-dashed px-4 py-5 text-center transition-colors',
        dragging
          ? 'border-accent bg-accent-soft'
          : 'border-line bg-surface hover:border-accent/60 hover:bg-accent-soft/50',
      )}
    >
      <UploadCloud
        className={clsx('size-7 transition-colors', dragging ? 'text-accent' : 'text-muted group-hover:text-accent')}
        aria-hidden
      />
      <span className="text-sm font-medium">{dragging ? 'Släpp för att ladda upp' : 'Dra hit PDF-filer'}</span>
      <span className="text-xs text-muted">eller klicka för att välja · max {formatBytes(MAX_UPLOAD_BYTES)}</span>
      <input
        ref={input}
        type="file"
        accept="application/pdf,.pdf"
        multiple
        hidden
        data-testid="file-input"
        onChange={(e) => {
          if (e.target.files) void handleFiles(e.target.files)
          e.target.value = ''
        }}
      />
    </button>
  )
}
