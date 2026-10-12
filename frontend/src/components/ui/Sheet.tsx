import { useEffect, useRef, type ReactNode } from 'react'
import { X } from 'lucide-react'
import { clsx } from 'clsx'

interface Props {
  open: boolean
  onClose: () => void
  title: string
  side: 'left' | 'right'
  /** Tailwind width classes for the panel. */
  widthClass?: string
  children: ReactNode
}

/** Slide-over dialog: closes on Escape/backdrop click, moves focus in and restores it on close. */
export function Sheet({ open, onClose, title, side, widthClass = 'w-[min(26rem,100vw)]', children }: Props) {
  const panel = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const previous = document.activeElement as HTMLElement | null
    panel.current?.focus()
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('keydown', onKey)
      previous?.focus?.()
    }
  }, [open, onClose])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-40 flex">
      <div className="animate-fade absolute inset-0 bg-black/40" onClick={onClose} aria-hidden />
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        className={clsx(
          'relative flex h-full flex-col bg-surface shadow-2xl outline-none',
          side === 'left' ? 'animate-slide-left mr-auto border-r' : 'animate-slide-right ml-auto border-l',
          'border-line',
          widthClass,
        )}
      >
        <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
          <h2 className="truncate text-sm font-semibold">{title}</h2>
          <button
            onClick={onClose}
            aria-label="Stäng"
            className="-m-1.5 rounded-lg p-1.5 text-muted hover:bg-surface-2 hover:text-fg"
          >
            <X className="size-5" />
          </button>
        </div>
        <div className="min-h-0 flex-1">{children}</div>
      </div>
    </div>
  )
}
