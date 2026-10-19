import { useCallback, useEffect, useRef, useState } from 'react'
import { ArrowUpRight, Eraser } from 'lucide-react'
import { useClearHistory, useDocuments, useHistory } from '../hooks/queries'
import { useChatStream } from '../hooks/useChatStream'
import type { ViewerTarget } from '../lib/types'
import { ChatTurn, LiveAnswer } from './ChatTurn'
import { Composer, type ComposerHandle } from './Composer'
import { APP_NAME, Logo } from './Logo'

// Questions that were checked against the Göteborg demo protocols (see eval/README.md): each has its
// answer in one or two places. Broad requests such as "summarise" or "list all" are not suggested
// because the model only sees five excerpts and answers them badly.
const DEMO_SUGGESTIONS = [
  'Vad beslutade kommunstyrelsen om investeringar i europeisk försvarsindustri?',
  'Vem anmälde jäv vid sammanträdet 2025-04-09?',
  'Vad blev beslutet om ökad kamerabevakning?',
]
// Templates for other documents: they fill in the question box instead of sending it.
const GENERIC_SUGGESTIONS = ['Vad beslutades om …', 'Vem förordnades som …']

/** Keeps the view pinned to the newest text, unless the reader has scrolled up to read something. */
function useStickToBottom(dependency: unknown) {
  const scroller = useRef<HTMLDivElement>(null)
  const pinned = useRef(true)

  const onScroll = useCallback(() => {
    const el = scroller.current
    if (el) pinned.current = el.scrollHeight - el.scrollTop - el.clientHeight < 96
  }, [])

  useEffect(() => {
    const el = scroller.current
    if (el && pinned.current) el.scrollTop = el.scrollHeight
  }, [dependency])

  const jumpToBottom = useCallback(() => {
    pinned.current = true
    const el = scroller.current
    if (el) el.scrollTop = el.scrollHeight
  }, [])

  return { scroller, onScroll, jumpToBottom }
}

export function ChatView({ onOpen }: { onOpen: (target: ViewerTarget) => void }) {
  const { data: history = [] } = useHistory()
  const { data: docs = [] } = useDocuments()
  const clear = useClearHistory()
  const { live, busy, send, stop, dismiss } = useChatStream()
  const [draft, setDraft] = useState('')
  const composer = useRef<ComposerHandle>(null)

  const hasReadyDocs = docs.some((d) => d.status === 'Ready')
  const hasDemoDocs = docs.some((d) => d.status === 'Ready' && /^K[SF]_protokoll_/.test(d.fileName))
  const suggestions = hasDemoDocs ? DEMO_SUGGESTIONS : GENERIC_SUGGESTIONS
  const last = history.at(-1)

  const { scroller, onScroll, jumpToBottom } = useStickToBottom(`${history.length}|${live?.text.length ?? -1}|${live?.phase}`)

  function ask(question: string) {
    jumpToBottom()
    void send(question)
  }

  function submit() {
    const question = draft
    setDraft('')
    ask(question)
  }

  const isEmpty = history.length === 0 && live === null

  return (
    <div className="flex h-full flex-col">
      <div ref={scroller} onScroll={onScroll} className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto flex min-h-full w-full max-w-3xl flex-col gap-7 px-4 pb-8 pt-6">
          {isEmpty ? (
            <div className="animate-rise my-auto flex flex-col items-center py-10 text-center">
              <Logo className="size-14" />
              <h1 className="mt-6 text-balance text-3xl font-semibold tracking-tight">Fråga dina kommundokument</h1>
              <p className="mt-3 max-w-md text-balance leading-relaxed text-muted">
                {hasReadyDocs
                  ? `${APP_NAME} svarar utifrån dina dokument och visar exakt vilken sida svaret kommer från.`
                  : 'Ladda upp ett eller flera PDF-dokument till vänster för att börja ställa frågor.'}
              </p>
              {hasReadyDocs && (
                <ul className="mt-8 flex w-full max-w-lg flex-col gap-2.5">
                  {suggestions.map((s) => (
                    <li key={s}>
                      <button
                        onClick={() => {
                          if (hasDemoDocs) ask(s)
                          else {
                            setDraft(s.split('…')[0])
                            composer.current?.focus()
                          }
                        }}
                        className="group flex w-full items-center justify-between gap-3 rounded-2xl border border-line bg-surface px-4 py-3.5 text-left text-[0.95rem] shadow-soft transition-all duration-[var(--dur)] hover:-translate-y-0.5 hover:border-accent/50 hover:shadow-lift"
                      >
                        <span>{s}</span>
                        <ArrowUpRight className="size-4 shrink-0 text-muted transition-colors group-hover:text-accent" aria-hidden />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ) : (
            <>
              {history.length > 0 && (
                <div className="flex justify-end">
                  <button
                    onClick={() => clear.mutate()}
                    disabled={clear.isPending || busy}
                    className="flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs text-muted transition-colors hover:bg-surface-2 hover:text-fg disabled:opacity-50"
                  >
                    <Eraser className="size-3.5" aria-hidden />
                    Ny konversation
                  </button>
                </div>
              )}
              {history.map((turn) => (
                <ChatTurn
                  key={turn.id}
                  turn={turn}
                  onOpen={onOpen}
                  onRegenerate={turn === last && live === null ? () => ask(turn.question) : undefined}
                />
              ))}
              {live && <LiveAnswer live={live} onOpen={onOpen} onRetry={() => ask(live.question)} onDismiss={dismiss} />}
            </>
          )}
        </div>
      </div>

      <div className="bg-gradient-to-t from-bg from-70% to-transparent px-4 pb-4 pt-2">
        <Composer
          ref={composer}
          value={draft}
          onChange={setDraft}
          onSubmit={submit}
          busy={busy}
          onStop={stop}
          onRecall={last ? () => setDraft(last.question) : undefined}
          disabled={!hasReadyDocs}
          placeholder={hasReadyDocs ? 'Ställ en fråga om dokumenten…' : 'Ladda upp ett dokument först'}
        />
        <p className="mx-auto mt-2.5 max-w-3xl text-center text-xs text-muted">
          Svaren genereras av en AI-modell. Kontrollera alltid mot källan.
        </p>
      </div>
    </div>
  )
}
