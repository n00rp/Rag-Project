import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, api } from './api'

function mockFetch(response: Response | Error) {
  vi.stubGlobal(
    'fetch',
    vi.fn(() => (response instanceof Error ? Promise.reject(response) : Promise.resolve(response))),
  )
}

afterEach(() => vi.unstubAllGlobals())

describe('api error handling', () => {
  it('uses the problem-details detail and exposes the machine-readable code', async () => {
    mockFetch(
      Response.json(
        { title: 'Service Unavailable', detail: 'AI-modellen är inte tillgänglig.', code: 'ai_unavailable' },
        { status: 503 },
      ),
    )

    const error = await api.history().catch((e: unknown) => e)

    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(503)
    expect((error as ApiError).message).toBe('AI-modellen är inte tillgänglig.')
    expect((error as ApiError).isAiUnavailable).toBe(true)
  })

  it('falls back to the title, then to a generic message', async () => {
    mockFetch(Response.json({ title: 'Ogiltig begäran.' }, { status: 400 }))
    await expect(api.listDocuments()).rejects.toThrow('Ogiltig begäran.')

    mockFetch(new Response('<html>boom</html>', { status: 502 }))
    await expect(api.listDocuments()).rejects.toThrow('Något gick fel (502).')
  })

  it('reports an unreachable server as a network error', async () => {
    mockFetch(new TypeError('Failed to fetch'))

    const error = await api.health().catch((e: unknown) => e)

    expect((error as ApiError).code).toBe('network')
    expect((error as ApiError).status).toBe(0)
  })

  it('treats 204 as success without a body', async () => {
    mockFetch(new Response(null, { status: 204 }))
    await expect(api.deleteDocument('abc')).resolves.toBeUndefined()
  })
})
