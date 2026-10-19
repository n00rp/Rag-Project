import type { ChatAnswer, ChatSource } from './types'

/** One event of a streamed answer (see ChatEndpoints.Stream in the API). */
export type StreamEvent =
  | { type: 'sources'; sources: ChatSource[] }
  | { type: 'token'; text: string }
  | { type: 'done'; message: ChatAnswer }
  | { type: 'error'; code?: string; message: string }

/**
 * Reads a response body made of newline-delimited JSON and yields each parsed line as soon as it is complete.
 * A chunk can end in the middle of a line (or of a multi-byte character), so the rest is kept for the next chunk.
 */
export async function* readNdjson<T>(body: ReadableStream<Uint8Array>): AsyncGenerator<T> {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      let newline = buffer.indexOf('\n')
      while (newline >= 0) {
        const line = buffer.slice(0, newline).trim()
        buffer = buffer.slice(newline + 1)
        if (line) yield JSON.parse(line) as T
        newline = buffer.indexOf('\n')
      }
    }
    const rest = (buffer + decoder.decode()).trim()
    if (rest) yield JSON.parse(rest) as T
  } finally {
    reader.releaseLock()
  }
}
