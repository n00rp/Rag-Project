import { ChevronDown, Info } from 'lucide-react'
import { formatTimestamp } from '../lib/format'
import type { ChatAnswer, ViewerTarget } from '../lib/types'
import { AnswerText } from './AnswerText'
import { Logo } from './Logo'
import { SourceCard } from './SourceCard'

interface Props {
  turn: ChatAnswer
  /** Expand the source list (used for the most recent answer). */
  expandSources: boolean
  onOpen: (target: ViewerTarget) => void
}

export function UserBubble({ text }: { text: string }) {
  return (
    <div className="animate-rise flex justify-end">
      <p className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-accent px-4 py-2.5 text-accent-fg">
        {text}
      </p>
    </div>
  )
}

export function AssistantRow({ children }: { children: React.ReactNode }) {
  return (
    <div className="animate-rise flex gap-3">
      <Logo className="mt-0.5 size-7 shrink-0" />
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  )
}

export function ChatTurn({ turn, expandSources, onOpen }: Props) {
  return (
    <>
      <UserBubble text={turn.question} />
      <AssistantRow>
        {turn.grounded ? (
          <AnswerText text={turn.answer} sources={turn.sources} onOpen={onOpen} />
        ) : (
          <div className="flex gap-2.5 rounded-xl bg-warn-soft p-3 text-warn">
            <Info className="mt-0.5 size-4 shrink-0" aria-hidden />
            <p className="text-sm leading-relaxed">{turn.answer}</p>
          </div>
        )}

        {turn.sources.length > 0 && (
          <details open={expandSources} className="group mt-3">
            <summary className="flex w-fit cursor-pointer list-none items-center gap-1 rounded-md text-xs font-medium text-muted hover:text-fg">
              <ChevronDown className="size-3.5 transition-transform group-open:rotate-180" aria-hidden />
              Källor ({turn.sources.length})
            </summary>
            <div className="mt-2 space-y-2">
              {turn.sources.map((s, i) => (
                <SourceCard key={`${s.documentId}-${s.page}-${i}`} index={i + 1} source={s} onOpen={onOpen} />
              ))}
            </div>
          </details>
        )}

        <p className="mt-2 text-xs text-muted">{formatTimestamp(turn.createdAt)}</p>
      </AssistantRow>
    </>
  )
}
