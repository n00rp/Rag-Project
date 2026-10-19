import { readNdjson, type StreamEvent } from './stream'
import type { ChatAnswer, DocumentDto, Health } from './types'

export class ApiError extends Error {
  status: number
  code?: string

  constructor(status: number, message: string, code?: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }

  /** The AI model/GPU machine is offline: not the user's fault and worth a friendlier message. */
  get isAiUnavailable() {
    return this.code === 'ai_unavailable'
  }
}

async function toApiError(res: Response): Promise<ApiError> {
  let message = `Något gick fel (${res.status}).`
  let code: string | undefined
  try {
    // The API answers with RFC 7807 problem details.
    const body = await res.json()
    if (typeof body.detail === 'string') message = body.detail
    else if (typeof body.title === 'string') message = body.title
    if (typeof body.code === 'string') code = body.code
  } catch {
    /* body was not JSON; keep the generic message */
  }
  return new ApiError(res.status, message, code)
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(path, init)
  } catch {
    throw new ApiError(0, 'Kan inte nå servern. Kontrollera anslutningen.', 'network')
  }
  if (!res.ok) throw await toApiError(res)
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T)
}

export const api = {
  listDocuments: () => request<DocumentDto[]>('/api/documents'),

  uploadDocument: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<DocumentDto>('/api/documents', { method: 'POST', body: form })
  },

  deleteDocument: (id: string) => request<void>(`/api/documents/${id}`, { method: 'DELETE' }),

  retryDocument: (id: string) =>
    request<DocumentDto>(`/api/documents/${id}/retry`, { method: 'POST' }),

  /**
   * The answer as it is written. Errors before the first event (offline model, bad request) are thrown as
   * ApiError; a failure in the middle arrives as an `error` event. Aborting `signal` stops the answer, and the
   * server then keeps what was written.
   */
  askStream: async function* (question: string, signal?: AbortSignal, documentIds?: string[]): AsyncGenerator<StreamEvent> {
    let res: Response
    try {
      res = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, documentIds }),
        signal,
      })
    } catch (e) {
      if (e instanceof DOMException && e.name === 'AbortError') throw e
      throw new ApiError(0, 'Kan inte nå servern. Kontrollera anslutningen.', 'network')
    }
    if (!res.ok) throw await toApiError(res)
    if (!res.body) throw new ApiError(0, 'Servern skickade inget svar.', 'network')
    yield* readNdjson<StreamEvent>(res.body)
  },

  history: () => request<ChatAnswer[]>('/api/chat/history'),

  clearHistory: () => request<void>('/api/chat/history', { method: 'DELETE' }),

  health: () => request<Health>('/health'),
}

export const documentFileUrl = (id: string) => `/api/documents/${id}/file`
