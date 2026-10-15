import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { AlertCircle, ArrowUp, Eraser, WifiOff } from 'lucide-react'
import { useAsk, useClearHistory, useDocuments, useHistory } from '../hooks/queries'
import { ApiError } from '../lib/api'
import type { ViewerTarget } from '../lib/types'
import { APP_NAME, Logo } from './Logo'
import { AssistantRow, ChatTurn, UserBubble } from './ChatTurn'

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

// Ollama unloads an idle model, and loading it again can take about half a minute.
const SLOW_AFTER_MS = 6000

function TypingIndicator() {
  const [slow, setSlow] = useState(false)
  useEffect(() => {
    const t = setTimeout(() => setSlow(true), SLOW_AFTER_MS)
    return () => clearTimeout(t)
  }, [])
  return (
    <div className="flex items-center gap-2 text-sm text-muted" role="status">
      <span className="flex gap-1" aria-hidden>
        <span className="typing-dot size-1.5 rounded-full bg-muted" />
        <span className="typing-dot size-1.5 rounded-full bg-muted" />
        <span className="typing-dot size-1.5 rounded-full bg-muted" />
      </span>
      {slow ? 'Modellen startar, det kan ta en halv minut första gången…' : 'Söker i dokumenten…'}
    </div>
  )
}

export function ChatView({ onOpen }: { onOpen: (target: ViewerTarget) => void }) {
  const { data: history = [] } = useHistory()
  const { data: docs = [] } = useDocuments()
  const ask = useAsk()
  const clear = useClearHistory()
  const [draft, setDraft] = useState('')
  const bottom = useRef<HTMLDivElement>(null)
  const textarea = useRef<HTMLTextAreaElement>(null)

  const hasReadyDocs = docs.some((d) => d.status === 'Ready')
  const hasDemoDocs = docs.some((d) => d.status === 'Ready' && /^K[SF]_protokoll_/.test(d.fileName))
  const suggestions = hasDemoDocs ? DEMO_SUGGESTIONS : GENERIC_SUGGESTIONS
  const canSend = hasReadyDocs && !ask.isPending && draft.trim().length > 0

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [history.length, ask.isPending])

  function send(question: string) {
    const q = question.trim()
    if (!q || ask.isPending) return
    setDraft('')
    if (textarea.current) textarea.current.style.height = 'auto'
    ask.mutate(q)
  }

  function fillDraft(text: string) {
    setDraft(text)
    textarea.current?.focus()
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    send(draft)
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      send(draft)
    }
  }

  const error = ask.error instanceof ApiError ? ask.error : ask.error ? new ApiError(0, 'Något gick fel.') : null
  const isEmpty = history.length === 0 && !ask.isPending && !error

  return (
    <div className="flex h-full flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto flex min-h-full w-full max-w-3xl flex-col gap-6 px-4 py-6">
          {isEmpty ? (
            <div className="my-auto flex flex-col items-center py-10 text-center">
              <Logo className="size-14" />
              <h1 className="mt-5 text-2xl font-semibold tracking-tight">Fråga dina kommundokument</h1>
              <p className="mt-2 max-w-md text-balance text-muted">
                {hasReadyDocs
                  ? `${APP_NAME} svarar utifrån dina dokument och visar exakt vilken sida svaret kommer från.`
                  : 'Ladda upp ett eller flera PDF-dokument till vänster för att börja ställa frågor.'}
              </p>
              {hasReadyDocs && (
                <div className="mt-6 flex w-full max-w-md flex-col gap-2">
                  {suggestions.map((s) => (
                    <button
                      key={s}
                      onClick={() => (hasDemoDocs ? send(s) : fillDraft(s.split('…')[0]))}
                      className="rounded-xl border border-line bg-surface px-4 py-3 text-left text-sm transition-colors hover:border-accent/60 hover:bg-accent-soft/40"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <>
              <div className="flex justify-end">
                <button
                  onClick={() => clear.mutate()}
                  disabled={clear.isPending || ask.isPending}
                  className="flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs text-muted transition-colors hover:bg-surface-2 hover:text-fg disabled:opacity-50"
                >
                  <Eraser className="size-3.5" aria-hidden />
                  Ny konversation
                </button>
              </div>
              {history.map((turn, i) => (
                <ChatTurn key={turn.id} turn={turn} expandSources={i === history.length - 1} onOpen={onOpen} />
              ))}
              {ask.isPending && (
                <>
                  <UserBubble text={ask.variables} />
                  <AssistantRow>
                    <TypingIndicator />
                  </AssistantRow>
                </>
              )}
              {error && !ask.isPending && (
                <AssistantRow>
                  <div
                    role="alert"
                    className="flex gap-2.5 rounded-xl bg-danger-soft p-3 text-sm text-danger"
                  >
                    {error.isAiUnavailable ? (
                      <WifiOff className="mt-0.5 size-4 shrink-0" aria-hidden />
                    ) : (
                      <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden />
                    )}
                    <div>
                      <p>{error.message}</p>
                      {ask.variables && (
                        <button
                          onClick={() => ask.mutate(ask.variables)}
                          className="mt-1 font-medium underline-offset-2 hover:underline"
                        >
                          Försök igen
                        </button>
                      )}
                    </div>
                  </div>
                </AssistantRow>
              )}
            </>
          )}
          <div ref={bottom} />
        </div>
      </div>

      <div className="border-t border-line bg-bg/80 px-4 pb-4 pt-3 backdrop-blur">
        <form
          onSubmit={onSubmit}
          className="mx-auto flex w-full max-w-3xl items-end gap-2 rounded-2xl border border-line bg-surface p-2 shadow-sm focus-within:border-accent"
        >
          <textarea
            ref={textarea}
            value={draft}
            rows={1}
            maxLength={2000}
            disabled={!hasReadyDocs}
            onChange={(e) => {
              setDraft(e.target.value)
              e.target.style.height = 'auto'
              e.target.style.height = `${Math.min(e.target.scrollHeight, 160)}px`
            }}
            onKeyDown={onKeyDown}
            aria-label="Din fråga"
            placeholder={hasReadyDocs ? 'Ställ en fråga om dokumenten…' : 'Ladda upp ett dokument först'}
            className="max-h-40 min-h-9 flex-1 resize-none bg-transparent px-2 py-1.5 outline-none placeholder:text-muted focus-visible:outline-none disabled:cursor-not-allowed"
          />
          <button
            type="submit"
            disabled={!canSend}
            aria-label="Skicka fråga"
            className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-accent text-accent-fg transition-colors hover:bg-accent-hover disabled:bg-surface-2 disabled:text-muted"
          >
            <ArrowUp className="size-5" />
          </button>
        </form>
        <p className="mx-auto mt-2 max-w-3xl text-center text-xs text-muted">
          Svaren genereras av en AI-modell. Kontrollera alltid mot källan.
        </p>
      </div>
    </div>
  )
}
