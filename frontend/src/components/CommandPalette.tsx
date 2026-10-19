import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { Search } from 'lucide-react'
import { clsx } from 'clsx'

export interface Command {
  id: string
  label: string
  /** A keyboard shortcut or short note shown on the right. */
  hint?: string
  run: () => void
}

interface Props {
  commands: Command[]
  onClose: () => void
}

/** Ctrl/Cmd+K: type to filter, arrows to move, Enter to run, Esc to close. Mounted only while open. */
export function CommandPalette({ commands, onClose }: Props) {
  const listId = useId()
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)
  const input = useRef<HTMLInputElement>(null)

  const shown = useMemo(() => {
    const q = query.trim().toLocaleLowerCase('sv')
    return q ? commands.filter((c) => c.label.toLocaleLowerCase('sv').includes(q)) : commands
  }, [commands, query])
  const current = Math.min(active, Math.max(shown.length - 1, 0))

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null
    input.current?.focus()
    return () => previous?.focus?.()
  }, [])

  function run(command: Command | undefined) {
    if (!command) return
    onClose()
    command.run()
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActive((i) => (shown.length ? (Math.min(i, shown.length - 1) + 1) % shown.length : 0))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActive((i) => (shown.length ? (Math.min(i, shown.length - 1) - 1 + shown.length) % shown.length : 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      run(shown[current])
    } else if (e.key === 'Escape') {
      e.preventDefault()
      onClose()
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center px-4 pt-[15vh]">
      <div className="animate-fade absolute inset-0 bg-black/40" onClick={onClose} aria-hidden />
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Kommandon"
        className="animate-rise relative w-full max-w-lg overflow-hidden rounded-2xl border border-line bg-surface shadow-lift"
      >
        <div className="flex items-center gap-2.5 border-b border-line px-4">
          <Search className="size-4 shrink-0 text-muted" aria-hidden />
          <input
            ref={input}
            value={query}
            onChange={(e) => {
              setQuery(e.target.value)
              setActive(0)
            }}
            onKeyDown={onKeyDown}
            role="combobox"
            aria-expanded="true"
            aria-controls={listId}
            aria-activedescendant={shown[current] ? `${listId}-${shown[current].id}` : undefined}
            aria-label="Sök kommando"
            placeholder="Vad vill du göra?"
            className="h-12 flex-1 bg-transparent outline-none placeholder:text-muted focus-visible:outline-none"
          />
        </div>
        <ul id={listId} role="listbox" aria-label="Kommandon" className="max-h-72 overflow-y-auto p-1.5">
          {shown.length === 0 && <li className="px-3 py-6 text-center text-sm text-muted">Inget kommando matchar.</li>}
          {shown.map((c, i) => (
            <li
              key={c.id}
              id={`${listId}-${c.id}`}
              role="option"
              aria-selected={i === current}
              onMouseMove={() => setActive(i)}
              onClick={() => run(c)}
              className={clsx(
                'flex cursor-pointer items-center justify-between gap-3 rounded-xl px-3 py-2.5 text-sm',
                i === current ? 'bg-accent-soft text-fg' : 'text-fg',
              )}
            >
              <span>{c.label}</span>
              {c.hint && <kbd className="rounded-md border border-line bg-surface-2 px-1.5 py-0.5 font-sans text-xs text-muted">{c.hint}</kbd>}
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
