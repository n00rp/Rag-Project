import { useState } from 'react'
import { AlertCircle, Check, Copy, Info, RotateCcw, WifiOff } from 'lucide-react'
import type { LiveTurn } from '../hooks/useChatStream'
import { formatTimestamp } from '../lib/format'
import type { ChatAnswer, ViewerTarget } from '../lib/types'
import { AnswerContent } from './AnswerContent'
import { Logo } from './Logo'
import { ProgressSteps } from './ProgressSteps'
import { SourceStrip } from './SourceStrip'

export function UserBubble({ text }: { text: string }) {
  return (
    <div className="animate-rise flex justify-end">
      <p className="max-w-[85%] whitespace-pre-wrap rounded-3xl rounded-br-lg bg-surface-2 px-4 py-2.5 leading-relaxed">
        {text}
      </p>
    </div>
  )
}

export function AssistantRow({ children }: { children: React.ReactNode }) {
  return (
    <div className="animate-rise flex gap-3.5">
      <Logo className="mt-1 size-7 shrink-0" />
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  )
}

function ActionButton({ onClick, label, children }: { onClick: () => void; label: string; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs text-muted transition-colors duration-[var(--dur-fast)] hover:bg-surface-2 hover:text-fg"
    >
      {children}
      {label}
    </button>
  )
}

function AnswerActions({ text, createdAt, interrupted, onRegenerate }: {
  text: string
  createdAt: string
  interrupted?: boolean
  onRegenerate?: () => void
}) {
  const [copied, setCopied] = useState(false)

  async function copy() {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 1600)
    } catch {
      /* clipboard can be blocked; nothing else to do */
    }
  }

  return (
    <div className="-ml-2 mt-2 flex flex-wrap items-center gap-0.5">
      <ActionButton onClick={copy} label={copied ? 'Kopierat' : 'Kopiera'}>
        {copied ? <Check className="size-3.5 text-ok" aria-hidden /> : <Copy className="size-3.5" aria-hidden />}
      </ActionButton>
      {onRegenerate && (
        <ActionButton onClick={onRegenerate} label="Svara igen">
          <RotateCcw className="size-3.5" aria-hidden />
        </ActionButton>
      )}
      <span className="ml-2 text-xs text-muted">
        {formatTimestamp(createdAt)}
        {interrupted && ' · avbruten'}
      </span>
    </div>
  )
}

interface TurnProps {
  turn: ChatAnswer
  onOpen: (target: ViewerTarget) => void
  /** Only given for the latest answer. */
  onRegenerate?: () => void
}

export function ChatTurn({ turn, onOpen, onRegenerate }: TurnProps) {
  return (
    <>
      <UserBubble text={turn.question} />
      <AssistantRow>
        {turn.grounded ? (
          <AnswerContent text={turn.answer} sources={turn.sources} onOpen={onOpen} />
        ) : (
          <div className="flex gap-2.5 rounded-2xl bg-warn-soft p-3.5 text-warn">
            <Info className="mt-0.5 size-4 shrink-0" aria-hidden />
            <p className="text-sm leading-relaxed">{turn.answer}</p>
          </div>
        )}
        {turn.interrupted && (
          <p className="mt-2 text-xs text-muted">Svaret avbröts innan det var klart.</p>
        )}
        <SourceStrip sources={turn.sources} onOpen={onOpen} />
        <AnswerActions text={turn.answer} createdAt={turn.createdAt} interrupted={turn.interrupted} onRegenerate={onRegenerate} />
      </AssistantRow>
    </>
  )
}

interface LiveProps {
  live: LiveTurn
  onOpen: (target: ViewerTarget) => void
  onRetry: () => void
  onDismiss: () => void
}

/** The answer that is being written right now (or that just failed). */
export function LiveAnswer({ live, onOpen, onRetry, onDismiss }: LiveProps) {
  const { error, text, phase, sources, stopped } = live
  const unreachable = error?.isAiUnavailable
  const writing = !error && !stopped

  return (
    <>
      <UserBubble text={live.question} />
      <AssistantRow>
        {text === '' && writing && <ProgressSteps phase={phase} sources={sources} />}

        {text !== '' && <AnswerContent text={text} sources={sources} onOpen={onOpen} streaming={writing} />}

        {stopped && <p className="mt-2 text-xs text-muted">Stoppad.</p>}

        {error && (
          <div role="alert" className="mt-3 flex gap-2.5 rounded-2xl bg-danger-soft p-3.5 text-sm text-danger">
            {unreachable ? <WifiOff className="mt-0.5 size-4 shrink-0" aria-hidden /> : <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden />}
            <div>
              <p>{error.message}</p>
              {text === '' && (
                <div className="mt-1.5 flex gap-3 font-medium">
                  <button onClick={onRetry} className="underline-offset-2 hover:underline">
                    Försök igen
                  </button>
                  <button onClick={onDismiss} className="underline-offset-2 hover:underline">
                    Stäng
                  </button>
                </div>
              )}
            </div>
          </div>
        )}
      </AssistantRow>
    </>
  )
}
