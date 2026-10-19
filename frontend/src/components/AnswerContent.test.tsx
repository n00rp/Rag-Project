import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { ChatSource } from '../lib/types'
import { AnswerContent, linkCitations } from './AnswerContent'

const sources: ChatSource[] = [
  { documentId: 'doc-a', fileName: 'protokoll-a.pdf', page: 4, snippet: 'Barn- och utbildningsnämnden beslutade', score: 0.9 },
  { documentId: 'doc-b', fileName: 'protokoll-b.pdf', page: 9, snippet: 'b', score: 0.8 },
  { documentId: 'doc-c', fileName: 'protokoll-c.pdf', page: 1, snippet: 'c', score: 0.7 },
]

describe('linkCitations', () => {
  it('turns [n] and [n, m] into citation links and leaves real links alone', () => {
    expect(linkCitations('A [1] B [2, 3] C [ref](https://x.se)')).toBe(
      'A [1](cite:1) B [2](cite:2) [3](cite:3) C [ref](https://x.se)',
    )
  })
})

describe('AnswerContent', () => {
  it('turns citation markers into buttons that open the cited page', async () => {
    const onOpen = vi.fn()
    render(<AnswerContent text="Skolskjuts införs [1] men bidrag minskar [2]." sources={sources} onOpen={onOpen} />)

    await userEvent.click(screen.getByRole('button', { name: /Källa 2: protokoll-b.pdf, sida 9/ }))

    expect(onOpen).toHaveBeenCalledWith({ documentId: 'doc-b', fileName: 'protokoll-b.pdf', page: 9, snippet: 'b' })
  })

  it('handles several citations in one bracket', () => {
    render(<AnswerContent text="Beslutet [1, 3] gäller." sources={sources} onOpen={vi.fn()} />)

    expect(screen.getAllByRole('button').map((b) => b.textContent)).toEqual(['1', '3'])
  })

  it('shows where a citation comes from when it is hovered', async () => {
    render(<AnswerContent text="Beslut [1]." sources={sources} onOpen={vi.fn()} />)

    await userEvent.hover(screen.getByRole('button', { name: /Källa 1/ }))

    const card = await screen.findByRole('tooltip')
    expect(card).toHaveTextContent('protokoll-a.pdf')
    expect(card).toHaveTextContent('sida 4')
    expect(card).toHaveTextContent('Barn- och utbildningsnämnden beslutade')
  })

  it('renders Swedish characters intact next to citations', () => {
    const swedish: ChatSource[] = [
      { documentId: 'doc-å', fileName: 'Östra Ängby – protokoll.pdf', page: 3, snippet: 'ö', score: 1 },
    ]
    render(<AnswerContent text="Nämnden beslutade om åk 1–6 i Östra Ängby [1]. ÅÄÖ åäö" sources={swedish} onOpen={vi.fn()} />)

    expect(screen.getByText(/Nämnden beslutade om åk 1–6 i Östra Ängby/)).toBeInTheDocument()
    expect(screen.getByText(/ÅÄÖ åäö/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Östra Ängby – protokoll.pdf, sida 3/ })).toBeInTheDocument()
  })

  it('leaves markers without a matching source as plain text', () => {
    render(<AnswerContent text="Okänd källa [7]." sources={sources} onOpen={vi.fn()} />)

    expect(screen.queryByRole('button')).not.toBeInTheDocument()
    expect(screen.getByText(/\[7\]/)).toBeInTheDocument()
  })

  it('renders Markdown: lists, bold text and tables', () => {
    const text = '**Beslut:**\n\n- Första\n- Andra\n\n| Nämnd | Belopp |\n|---|---|\n| Grundskola | 6 mnkr |'
    render(<AnswerContent text={text} sources={sources} onOpen={vi.fn()} />)

    expect(screen.getByText('Beslut:').tagName).toBe('STRONG')
    expect(screen.getAllByRole('listitem').map((li) => li.textContent)).toEqual(['Första', 'Andra'])
    expect(screen.getByRole('table')).toHaveTextContent('Grundskola')
  })

  it('does not render raw HTML or run script links from the model', () => {
    const text = '<img src=x onerror="alert(1)"> [klicka](javascript:alert(1)) <script>alert(2)</script>'
    const { container } = render(<AnswerContent text={text} sources={sources} onOpen={vi.fn()} />)

    expect(container.querySelector('img, script')).toBeNull()
    const link = container.querySelector('a')
    expect(link?.getAttribute('href') ?? '').not.toMatch(/^javascript:/i)
  })

  it('marks the answer as streaming so a caret can be drawn', () => {
    const { container } = render(<AnswerContent text="Text" sources={[]} onOpen={vi.fn()} streaming />)

    expect(container.firstElementChild).toHaveClass('streaming')
  })
})
