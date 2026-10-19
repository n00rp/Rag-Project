import { memo } from 'react'
import Markdown, { defaultUrlTransform } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { ChatSource, ViewerTarget } from '../lib/types'
import { CitationChip } from './CitationChip'

interface Props {
  text: string
  sources: ChatSource[]
  onOpen: (target: ViewerTarget) => void
  /** The answer is still being written: show a caret after the last word. */
  streaming?: boolean
}

/** "[1]" and "[1, 3]" become links to a `cite:` address that is drawn as a citation chip. */
export function linkCitations(text: string): string {
  return text
    .replace(/\[(\d+(?:\s*,\s*\d+)+)\](?!\()/g, (_, list: string) =>
      list.split(',').map((n) => `[${n.trim()}](cite:${n.trim()})`).join(' '))
    .replace(/\[(\d{1,3})\](?!\()/g, '[$1](cite:$1)')
}

/**
 * The answer as Markdown (lists, bold, tables) with numbered citations that open the cited page.
 * Raw HTML in the text is not rendered, and only http(s)/mailto links and our own `cite:` links are kept.
 */
export const AnswerContent = memo(function AnswerContent({ text, sources, onOpen, streaming }: Props) {
  return (
    <div className={streaming ? 'prose-answer streaming' : 'prose-answer'}>
      <Markdown
        remarkPlugins={[remarkGfm]}
        urlTransform={(url) => (url.startsWith('cite:') ? url : defaultUrlTransform(url))}
        components={{
          a({ href, children }) {
            if (href?.startsWith('cite:')) {
              const index = Number(href.slice('cite:'.length))
              const source = sources[index - 1]
              // A number the model made up (no such source) stays plain text.
              return source ? <CitationChip index={index} source={source} onOpen={onOpen} /> : <>[{index}]</>
            }
            return (
              <a href={href} target="_blank" rel="noreferrer noopener">
                {children}
              </a>
            )
          },
        }}
      >
        {linkCitations(text)}
      </Markdown>
    </div>
  )
})
