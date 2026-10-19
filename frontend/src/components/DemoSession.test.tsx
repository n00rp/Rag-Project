import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { DemoSession } from './DemoSession'

afterEach(() => vi.unstubAllGlobals())

const recording = {
  recordedAt: '2026-10-19T17:21:51+00:00',
  model: 'gemma3:12b',
  turns: [
    {
      id: 'demo-1', question: 'Vem anmälde jäv?', answer: 'Hampus Magnusson (M) anmälde jäv [1].', grounded: true,
      createdAt: '2026-10-19T17:21:51+00:00',
      sources: [{ documentId: 'd1', fileName: 'KS_protokoll_20250409.pdf', page: 3, snippet: 'Hampus Magnusson anmäler jäv', score: 0.9 }],
    },
    { id: 'demo-2', question: 'Vad gäller ärende SLK-2030-00001?', answer: 'Jag hittar inget stöd för det i dokumenten.', grounded: false, sources: [], createdAt: '2026-10-19T17:21:51+00:00' },
  ],
}

describe('DemoSession', () => {
  it('shows the recorded questions and answers, with the model and that they are saved', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(Response.json(recording))))
    render(<DemoSession onClose={() => {}} />)

    expect(await screen.findByText('Vem anmälde jäv?')).toBeInTheDocument()
    expect(screen.getByText(/Hampus Magnusson \(M\) anmälde jäv/)).toBeInTheDocument()
    expect(screen.getByText('Jag hittar inget stöd för det i dokumenten.')).toBeInTheDocument()
    expect(screen.getByText('gemma3:12b')).toBeInTheDocument()
    expect(screen.getByText(/Det här är sparade svar/)).toBeInTheDocument()
  })

  it('lets the reader point at a source but does not offer to open it', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(Response.json(recording))))
    render(<DemoSession onClose={() => {}} />)

    await userEvent.hover(await screen.findByRole('button', { name: /Källa 1: KS_protokoll_20250409.pdf, sida 3/ }))

    const card = await screen.findByRole('tooltip')
    expect(card).toHaveTextContent('Hampus Magnusson anmäler jäv')
    expect(card).not.toHaveTextContent('Klicka för att öppna')
  })

  it('says so when there is no recording in this version, and closes on request', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response('nope', { status: 404 }))))
    const onClose = vi.fn()
    render(<DemoSession onClose={onClose} />)

    expect(await screen.findByText('Det finns ingen inspelad session i den här versionen.')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Stäng' }))
    expect(onClose).toHaveBeenCalled()
  })
})
