import { useState, type FormEvent } from 'react'
import { ThumbsDown, ThumbsUp } from 'lucide-react'
import { clsx } from 'clsx'
import type { ChatAnswer, Rating } from '../lib/types'

interface Props {
  turn: ChatAnswer
  onRate: (rating: Rating | null, comment?: string) => void
}

function Thumb({ active, label, onClick, children, tone }: {
  active: boolean
  label: string
  onClick: () => void
  children: React.ReactNode
  tone: 'ok' | 'danger'
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      aria-label={label}
      title={label}
      className={clsx(
        'rounded-lg p-1.5 transition-colors duration-[var(--dur-fast)] hover:bg-surface-2',
        active ? (tone === 'ok' ? 'text-ok' : 'text-danger') : 'text-muted hover:text-fg',
      )}
    >
      {children}
    </button>
  )
}

/** Thumbs up/down on an answer. A thumbs down is saved at once and offers an optional note about what was wrong. */
export function FeedbackButtons({ turn, onRate }: Props) {
  const rating = turn.rating ?? null
  const [asking, setAsking] = useState(false)
  const [comment, setComment] = useState(turn.feedbackComment ?? '')

  function toggle(next: Rating) {
    if (rating === next) {
      setAsking(false)
      onRate(null)
      return
    }
    onRate(next)
    setAsking(next === 'down')
  }

  function submit(e: FormEvent) {
    e.preventDefault()
    onRate('down', comment)
    setAsking(false)
  }

  return (
    <>
      <Thumb active={rating === 'up'} label="Bra svar" onClick={() => toggle('up')} tone="ok">
        <ThumbsUp className="size-3.5" aria-hidden />
      </Thumb>
      <Thumb active={rating === 'down'} label="Dåligt svar" onClick={() => toggle('down')} tone="danger">
        <ThumbsDown className="size-3.5" aria-hidden />
      </Thumb>
      {asking && (
        <form onSubmit={submit} className="animate-fade ml-1 flex w-full items-center gap-2 pt-1.5 sm:w-auto sm:pt-0">
          <input
            autoFocus
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            maxLength={1000}
            aria-label="Vad var fel?"
            placeholder="Vad var fel? (valfritt)"
            className="min-w-0 flex-1 rounded-lg border border-line bg-surface px-2.5 py-1 text-xs outline-none focus:border-accent sm:w-56"
          />
          <button type="submit" className="rounded-lg bg-surface-2 px-2.5 py-1 text-xs font-medium hover:bg-line">
            Skicka
          </button>
        </form>
      )}
    </>
  )
}
