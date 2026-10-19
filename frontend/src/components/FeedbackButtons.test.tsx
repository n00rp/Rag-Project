import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { ChatAnswer } from '../lib/types'
import { FeedbackButtons } from './FeedbackButtons'

const turn = (extra: Partial<ChatAnswer> = {}): ChatAnswer => ({
  id: 'a1', question: 'Fråga?', answer: 'Svar.', grounded: true, sources: [], createdAt: '2025-01-01T10:00:00Z', ...extra,
})

describe('FeedbackButtons', () => {
  it('rates up, and withdraws the rating when the same thumb is pressed again', async () => {
    const onRate = vi.fn()
    const { rerender } = render(<FeedbackButtons turn={turn()} onRate={onRate} />)

    await userEvent.click(screen.getByRole('button', { name: 'Bra svar' }))
    expect(onRate).toHaveBeenLastCalledWith('up')

    rerender(<FeedbackButtons turn={turn({ rating: 'up' })} onRate={onRate} />)
    expect(screen.getByRole('button', { name: 'Bra svar' })).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(screen.getByRole('button', { name: 'Bra svar' }))
    expect(onRate).toHaveBeenLastCalledWith(null)
  })

  it('saves a thumbs down at once and then offers an optional note', async () => {
    const onRate = vi.fn()
    render(<FeedbackButtons turn={turn()} onRate={onRate} />)

    await userEvent.click(screen.getByRole('button', { name: 'Dåligt svar' }))
    expect(onRate).toHaveBeenLastCalledWith('down')

    await userEvent.type(screen.getByLabelText('Vad var fel?'), 'Fel belopp')
    await userEvent.click(screen.getByRole('button', { name: 'Skicka' }))

    expect(onRate).toHaveBeenLastCalledWith('down', 'Fel belopp')
    expect(screen.queryByLabelText('Vad var fel?')).not.toBeInTheDocument()
  })

  it('shows an earlier rating when the page is reloaded', () => {
    render(<FeedbackButtons turn={turn({ rating: 'down', feedbackComment: 'Fel sida' })} onRate={vi.fn()} />)

    expect(screen.getByRole('button', { name: 'Dåligt svar' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'Bra svar' })).toHaveAttribute('aria-pressed', 'false')
  })
})
