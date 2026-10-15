import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { ChatSource } from '../lib/types'
import { AnswerText } from './AnswerText'

const sources: ChatSource[] = [
  { documentId: 'doc-a', fileName: 'protokoll-a.pdf', page: 4, snippet: 'a', score: 0.9 },
  { documentId: 'doc-b', fileName: 'protokoll-b.pdf', page: 9, snippet: 'b', score: 0.8 },
]

describe('AnswerText', () => {
  it('turns citation markers into buttons that open the cited page', async () => {
    const onOpen = vi.fn()
    render(<AnswerText text="Skolskjuts införs [1] men bidrag minskar [2]." sources={sources} onOpen={onOpen} />)

    await userEvent.click(screen.getByRole('button', { name: /Källa 2: protokoll-b.pdf, sida 9/ }))

    expect(onOpen).toHaveBeenCalledWith({ documentId: 'doc-b', fileName: 'protokoll-b.pdf', page: 9, snippet: 'b' })
  })

  it('renders Swedish characters intact next to citations', () => {
    const swedish: ChatSource[] = [
      { documentId: 'doc-å', fileName: 'Östra Ängby – protokoll.pdf', page: 3, snippet: 'ö', score: 1 },
    ]
    render(<AnswerText text="Nämnden beslutade om åk 1–6 i Östra Ängby [1]. ÅÄÖ åäö" sources={swedish} onOpen={vi.fn()} />)

    expect(screen.getByText(/Nämnden beslutade om åk 1–6 i Östra Ängby/)).toBeInTheDocument()
    expect(screen.getByText(/ÅÄÖ åäö/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Östra Ängby – protokoll.pdf, sida 3/ })).toBeInTheDocument()
  })

  it('leaves markers without a matching source as plain text', () => {
    render(<AnswerText text="Okänd källa [7]." sources={sources} onOpen={vi.fn()} />)

    expect(screen.queryByRole('button')).not.toBeInTheDocument()
    expect(screen.getByText(/\[7\]/)).toBeInTheDocument()
  })
})
