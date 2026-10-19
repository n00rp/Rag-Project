import { forwardRef, useImperativeHandle, useRef, type FormEvent, type KeyboardEvent } from 'react'
import { ArrowUp, Square } from 'lucide-react'
import { clsx } from 'clsx'

export interface ComposerHandle {
  focus: () => void
}

interface Props {
  value: string
  onChange: (value: string) => void
  onSubmit: () => void
  /** An answer is being written: the send button becomes a stop button. */
  busy: boolean
  onStop: () => void
  /** Called on ArrowUp in an empty box, to bring back the previous question. */
  onRecall?: () => void
  disabled: boolean
  placeholder: string
}

const MAX_HEIGHT = 200

/** The question box: grows with the text, Enter sends, Shift+Enter breaks the line, Esc stops an answer. */
export const Composer = forwardRef<ComposerHandle, Props>(function Composer(
  { value, onChange, onSubmit, busy, onStop, onRecall, disabled, placeholder },
  ref,
) {
  const textarea = useRef<HTMLTextAreaElement>(null)
  useImperativeHandle(ref, () => ({ focus: () => textarea.current?.focus() }))

  const canSend = !disabled && !busy && value.trim().length > 0

  function resize(el: HTMLTextAreaElement) {
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, MAX_HEIGHT)}px`
  }

  function submit(e?: FormEvent) {
    e?.preventDefault()
    if (!canSend) return
    onSubmit()
    if (textarea.current) textarea.current.style.height = 'auto'
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      submit()
    } else if (e.key === 'Escape' && busy) {
      onStop()
    } else if (e.key === 'ArrowUp' && value === '' && onRecall) {
      e.preventDefault()
      onRecall()
    }
  }

  return (
    <form
      onSubmit={submit}
      className="mx-auto flex w-full max-w-3xl items-end gap-2 rounded-3xl border border-line bg-surface p-2 pl-4 shadow-lift transition-colors duration-[var(--dur)] focus-within:border-accent/70"
    >
      <textarea
        ref={textarea}
        value={value}
        rows={1}
        maxLength={2000}
        disabled={disabled}
        onChange={(e) => {
          onChange(e.target.value)
          resize(e.target)
        }}
        onKeyDown={onKeyDown}
        aria-label="Din fråga"
        placeholder={placeholder}
        className="max-h-52 min-h-10 flex-1 resize-none bg-transparent py-2 leading-relaxed outline-none placeholder:text-muted focus-visible:outline-none disabled:cursor-not-allowed"
      />
      {busy ? (
        <button
          type="button"
          onClick={onStop}
          aria-label="Stoppa svaret"
          title="Stoppa (Esc)"
          className="flex size-10 shrink-0 items-center justify-center rounded-full bg-fg text-bg transition-transform duration-[var(--dur-fast)] hover:scale-105"
        >
          <Square className="size-3.5 fill-current" aria-hidden />
        </button>
      ) : (
        <button
          type="submit"
          disabled={!canSend}
          aria-label="Skicka fråga"
          className={clsx(
            'flex size-10 shrink-0 items-center justify-center rounded-full text-accent-fg transition-all duration-[var(--dur)]',
            canSend ? 'bg-[image:var(--grad)] shadow-soft hover:scale-105' : 'bg-surface-2 text-muted',
          )}
        >
          <ArrowUp className="size-5" aria-hidden />
        </button>
      )}
    </form>
  )
})
