import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { ChatAnswer, DocumentDto } from '../lib/types'
import { ChatView } from './ChatView'

afterEach(() => vi.unstubAllGlobals())

const doc = (fileName: string): DocumentDto => ({
  id: fileName, fileName, sizeBytes: 1, status: 'Ready', error: null, pageCount: 1, chunkCount: 1, createdAt: '2025-01-01',
})
const answer: ChatAnswer = {
  id: 'a1', question: 'Vad?', answer: 'Svar.', grounded: true, sources: [], createdAt: '2025-01-01T10:00:00Z',
}

const ndjson = (...events: object[]) => events.map((e) => JSON.stringify(e) + '\n').join('')

function renderChat(docs: DocumentDto[], history: ChatAnswer[] = []) {
  const calls: string[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string, init?: RequestInit) => {
      calls.push(`${init?.method ?? 'GET'} ${url}`)
      if (init?.method === 'DELETE') return Promise.resolve(new Response(null, { status: 204 }))
      if (init?.method === 'POST') return Promise.resolve(new Response(ndjson(
        { type: 'sources', sources: [] },
        { type: 'token', text: 'Svar.' },
        { type: 'done', message: answer },
      )))
      return Promise.resolve(Response.json(url.includes('documents') ? docs : history))
    }),
  )
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <ChatView onOpen={() => {}} />
    </QueryClientProvider>,
  )
  return calls
}

describe('ChatView', () => {
  it('suggests verified questions when the demo protocols are loaded and sends one on click', async () => {
    const calls = renderChat([doc('KS_protokoll_20250409.pdf')])
    await userEvent.click(await screen.findByRole('button', { name: /europeisk försvarsindustri/ }))
    await waitFor(() => expect(calls).toContain('POST /api/chat/stream'))
  })

  it('offers fill-in templates for other documents instead of sending a question', async () => {
    const calls = renderChat([doc('annat.pdf')])
    await userEvent.click(await screen.findByRole('button', { name: 'Vad beslutades om …' }))
    expect(screen.getByLabelText('Din fråga')).toHaveValue('Vad beslutades om ')
    expect(calls).not.toContain('POST /api/chat/stream')
  })

  it('clears the conversation with "Ny konversation"', async () => {
    const calls = renderChat([doc('annat.pdf')], [answer])
    await screen.findByText('Svar.')
    await userEvent.click(screen.getByRole('button', { name: /Ny konversation/ }))
    await waitFor(() => expect(calls).toContain('DELETE /api/chat/history'))
    await waitFor(() => expect(screen.queryByText('Svar.')).not.toBeInTheDocument())
  })
})
