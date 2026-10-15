import { Fragment } from 'react'
import type { ChatSource, ViewerTarget } from '../lib/types'

interface Props {
  text: string
  sources: ChatSource[]
  onOpen: (target: ViewerTarget) => void
}

/** Renders the answer and turns "[2]" markers into clickable chips that open the cited page. */
export function AnswerText({ text, sources, onOpen }: Props) {
  const parts = text.split(/(\[\d+\])/g)

  return (
    <p className="whitespace-pre-wrap leading-relaxed">
      {parts.map((part, i) => {
        const match = /^\[(\d+)\]$/.exec(part)
        const source = match ? sources[Number(match[1]) - 1] : undefined
        if (!match || !source) return <Fragment key={i}>{part}</Fragment>

        return (
          <button
            key={i}
            type="button"
            onClick={() => onOpen({ documentId: source.documentId, fileName: source.fileName, page: source.page, snippet: source.snippet })}
            title={`${source.fileName}, sida ${source.page}`}
            aria-label={`Källa ${match[1]}: ${source.fileName}, sida ${source.page}`}
            className="mx-0.5 inline-flex size-5 -translate-y-px items-center justify-center rounded-md bg-accent-soft align-middle text-xs font-semibold text-accent hover:bg-accent hover:text-accent-fg"
          >
            {match[1]}
          </button>
        )
      })}
    </p>
  )
}
