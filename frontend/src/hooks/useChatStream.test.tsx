import type { ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { ChatAnswer } from '../lib/types'
import { useChatStream } from './useChatStream'

afterEach(() => vi.unstubAllGlobals())

const saved = (answer: string, extra: Partial<ChatAnswer> = {}): ChatAnswer => ({
  id: crypto.randomUUID(), question: 'Fråga?', answer, grounded: true, sources: [], createdAt: '2025-01-01T10:00:00Z', ...extra,
})
const source = { documentId: 'd1', fileName: 'a.pdf', page: 2, snippet: 'utdrag', score: 0.9 }

/** A fetch whose answer stream is driven by the test, and that reacts to being aborted like the real one. */
function controllableAnswer(history: () => ChatAnswer[] = () => []) {
  let push!: (event: object) => void
  let end!: () => void
  let abort: () => void = () => {}
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      const encoder = new TextEncoder()
      push = (event) => controller.enqueue(encoder.encode(JSON.stringify(event) + '\n'))
      end = () => controller.close()
      abort = () => controller.error(new DOMException('stopped', 'AbortError'))
    },
  })
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string, init?: RequestInit) => {
      if (url === '/api/chat/history') return Promise.resolve(Response.json(history()))
      init?.signal?.addEventListener('abort', () => abort())
      return Promise.resolve(new Response(stream, { status: 200 }))
    }),
  )
  return { push, end }
}

function setup() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  client.setQueryData<ChatAnswer[]>(['history'], [])
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>
  return { client, ...renderHook(() => useChatStream(), { wrapper }) }
}

describe('useChatStream', () => {
  it('follows the answer from searching to writing and adds the saved message to the history when it is done', async () => {
    const answer = controllableAnswer()
    const { result, client } = setup()

    act(() => void result.current.send('Fråga?'))
    expect(result.current.live).toMatchObject({ question: 'Fråga?', phase: 'searching', text: '' })
    expect(result.current.busy).toBe(true)

    act(() => answer.push({ type: 'sources', sources: [source] }))
    await waitFor(() => expect(result.current.live?.phase).toBe('reading'))
    expect(result.current.live?.sources).toHaveLength(1)

    act(() => answer.push({ type: 'token', text: 'Hej ' }))
    act(() => answer.push({ type: 'token', text: 'där' }))
    await waitFor(() => expect(result.current.live).toMatchObject({ phase: 'writing', text: 'Hej där' }))

    const message = saved('Hej där')
    act(() => {
      answer.push({ type: 'done', message })
      answer.end()
    })
    await waitFor(() => expect(result.current.live).toBeNull())
    expect(client.getQueryData<ChatAnswer[]>(['history'])).toEqual([message])
    expect(result.current.busy).toBe(false)
  })

  it('remembers when the model says the documents only partly support the answer', async () => {
    const answer = controllableAnswer()
    const { result } = setup()

    act(() => void result.current.send('Fråga?'))
    act(() => answer.push({ type: 'support', level: 'delvis' }))

    await waitFor(() => expect(result.current.live?.support).toBe('delvis'))
    act(() => result.current.stop())
  })

  it('keeps the text on screen when stopped, until the server-side saved partial answer can be fetched', async () => {
    const partial = saved('Det här hann ', { interrupted: true })
    let serverHasIt = false
    const answer = controllableAnswer(() => (serverHasIt ? [partial] : []))
    const { result, client } = setup()

    act(() => void result.current.send('Fråga?'))
    act(() => answer.push({ type: 'token', text: 'Det här hann ' }))
    await waitFor(() => expect(result.current.live?.text).toBe('Det här hann '))

    act(() => result.current.stop())
    await waitFor(() => expect(result.current.live?.stopped).toBe(true))
    expect(result.current.live?.text).toBe('Det här hann ') // still visible, nothing flickers

    serverHasIt = true
    await waitFor(() => expect(result.current.live).toBeNull(), { timeout: 3000 })
    expect(client.getQueryData<ChatAnswer[]>(['history'])).toEqual([partial])
  })

  it('shows an unreachable model as an error that can be retried, and saves nothing', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(Response.json({ title: 'nere', code: 'ai_unavailable' }, { status: 503 }))))
    const { result, client } = setup()

    await act(async () => result.current.send('Fråga?'))

    expect(result.current.live?.error?.isAiUnavailable).toBe(true)
    expect(result.current.busy).toBe(false)
    expect(client.getQueryData<ChatAnswer[]>(['history'])).toEqual([])

    act(() => result.current.dismiss())
    expect(result.current.live).toBeNull()
  })

  it('keeps the partial answer when the model fails halfway', async () => {
    const partial = saved('Halva svaret', { interrupted: true })
    const answer = controllableAnswer(() => [partial])
    const { result, client } = setup()

    act(() => void result.current.send('Fråga?'))
    act(() => answer.push({ type: 'token', text: 'Halva svaret' }))
    act(() => answer.push({ type: 'error', code: 'ai_unavailable', message: 'Modellen slutade svara.' }))
    await waitFor(() => expect(result.current.live?.error?.message).toBe('Modellen slutade svara.'))

    await waitFor(() => expect(result.current.live).toBeNull(), { timeout: 3000 })
    expect(client.getQueryData<ChatAnswer[]>(['history'])).toEqual([partial])
  })

  it('ignores a new question while an answer is being written', async () => {
    controllableAnswer()
    const { result } = setup()

    act(() => void result.current.send('Första?'))
    act(() => void result.current.send('Andra?'))

    expect(result.current.live?.question).toBe('Första?')
    act(() => result.current.stop())
  })
})
