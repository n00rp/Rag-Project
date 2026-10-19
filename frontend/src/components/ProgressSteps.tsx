import { useEffect, useState } from 'react'
import { Check } from 'lucide-react'
import { clsx } from 'clsx'
import type { Phase } from '../hooks/useChatStream'
import { pluralize } from '../lib/format'
import type { ChatSource } from '../lib/types'

// Ollama unloads an idle model, and loading it again can take about half a minute.
const SLOW_AFTER_MS = 6000

function Step({ state, children }: { state: 'done' | 'active' | 'todo'; children: React.ReactNode }) {
  return (
    <li className={clsx('flex items-center gap-2.5 text-sm transition-colors', state === 'todo' ? 'text-muted/60' : state === 'active' ? 'text-fg' : 'text-muted')}>
      <span
        className={clsx(
          'flex size-4 shrink-0 items-center justify-center rounded-full',
          state === 'done' && 'bg-ok-soft text-ok',
          state === 'active' && 'bg-accent-soft',
          state === 'todo' && 'border border-line',
        )}
        aria-hidden
      >
        {state === 'done' ? (
          <Check className="size-3" strokeWidth={3} />
        ) : state === 'active' ? (
          <span className="flex gap-0.5">
            <span className="typing-dot size-1 rounded-full bg-accent" />
            <span className="typing-dot size-1 rounded-full bg-accent" />
            <span className="typing-dot size-1 rounded-full bg-accent" />
          </span>
        ) : null}
      </span>
      {children}
    </li>
  )
}

/** What the system is doing before the first word of the answer: searching, reading what it found, writing. */
export function ProgressSteps({ phase, sources }: { phase: Phase; sources: ChatSource[] }) {
  const [slow, setSlow] = useState(false)
  useEffect(() => {
    const t = setTimeout(() => setSlow(true), SLOW_AFTER_MS)
    return () => clearTimeout(t)
  }, [])

  const documents = new Set(sources.map((s) => s.documentId)).size
  const found = sources.length > 0

  return (
    <div role="status" aria-live="polite" className="animate-fade">
      <ol className="space-y-1.5">
        <Step state={phase === 'searching' ? 'active' : 'done'}>
          {found ? `Hittade ${pluralize(sources.length, 'utdrag', 'utdrag')} i ${pluralize(documents, 'dokument', 'dokument')}` : 'Söker i dokumenten'}
        </Step>
        <Step state={phase === 'reading' ? 'active' : phase === 'writing' ? 'done' : 'todo'}>Läser utdragen</Step>
        <Step state={phase === 'writing' ? 'active' : 'todo'}>Skriver svaret</Step>
      </ol>
      {slow && <p className="mt-2 text-xs text-muted">Modellen startar, det kan ta en halv minut första gången.</p>}
    </div>
  )
}
