import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError } from './api'
import { readNdjson, type StreamEvent } from './stream'

afterEach(() => vi.unstubAllGlobals())

function bodyOf(...chunks: (string | Uint8Array)[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder()
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(typeof chunk === 'string' ? encoder.encode(chunk) : chunk)
      controller.close()
    },
  })
}

async function collect<T>(iterable: AsyncIterable<T>): Promise<T[]> {
  const out: T[] = []
  for await (const item of iterable) out.push(item)
  return out
}

describe('readNdjson', () => {
  it('yields one object per line, also when a line is split over several chunks', async () => {
    const body = bodyOf('{"a":1}\n{"b"', ':2}\n', '{"c":3}\n')

    expect(await collect(readNdjson(body))).toEqual([{ a: 1 }, { b: 2 }, { c: 3 }])
  })

  it('keeps Swedish characters that are split in the middle of a multi-byte sequence', async () => {
    const bytes = new TextEncoder().encode('{"text":"Östra Ängby åäö"}\n')
    const cut = bytes.indexOf(0xc3) + 1 // between the two bytes of "Ö"

    const events = await collect(readNdjson<{ text: string }>(bodyOf(bytes.slice(0, cut), bytes.slice(cut))))

    expect(events).toEqual([{ text: 'Östra Ängby åäö' }])
  })

  it('reads a last line that has no trailing newline and ignores blank lines', async () => {
    expect(await collect(readNdjson(bodyOf('\n{"a":1}\n\n{"b":2}')))).toEqual([{ a: 1 }, { b: 2 }])
  })
})

describe('api.askStream', () => {
  it('yields the events of the answer in order', async () => {
    const lines = [
      { type: 'token', text: 'Hej' },
      { type: 'done', message: { id: '1', answer: 'Hej' } },
    ]
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response(bodyOf(lines.map((l) => JSON.stringify(l) + '\n').join('')), { status: 200 }))))

    const events = await collect<StreamEvent>(api.askStream('Fråga?'))

    expect(events.map((e) => e.type)).toEqual(['token', 'done'])
  })

  it('throws the problem details of an error before the stream starts (offline model)', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(Response.json({ title: 'AI nere', code: 'ai_unavailable' }, { status: 503 }))))

    const failure = await collect(api.askStream('Fråga?')).catch((e) => e)

    expect(failure).toBeInstanceOf(ApiError)
    expect(failure.isAiUnavailable).toBe(true)
  })

  it('reports a network failure as an ApiError, but lets an abort through unchanged', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new TypeError('Failed to fetch'))))
    expect(await collect(api.askStream('x')).catch((e) => e)).toMatchObject({ code: 'network' })

    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new DOMException('stopped', 'AbortError'))))
    const aborted = await collect(api.askStream('x')).catch((e) => e)
    expect(aborted).toBeInstanceOf(DOMException)
    expect(aborted.name).toBe('AbortError')
  })
})
