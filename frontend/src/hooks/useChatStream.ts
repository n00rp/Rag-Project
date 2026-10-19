import { useCallback, useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api, ApiError } from '../lib/api'
import type { ChatAnswer, ChatSource } from '../lib/types'

/** Where a live answer is: no sources yet / sources found, model not started / model is writing. */
export type Phase = 'searching' | 'reading' | 'writing'

export interface LiveTurn {
  question: string
  text: string
  sources: ChatSource[]
  phase: Phase
  /** Set when the answer could not be produced (or broke off). */
  error: ApiError | null
  /** The user stopped it; the server keeps what was written and the turn is replaced by the saved one. */
  stopped: boolean
}

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

/**
 * Asks a question and follows the answer while it is written. When it finishes, the saved message is added to the
 * history and the live turn disappears. If the user stops it (or the model fails halfway) the server has saved
 * the partial answer; the live turn stays on screen until that saved message can be fetched, so nothing flickers.
 */
export function useChatStream() {
  const qc = useQueryClient()
  const [live, setLive] = useState<LiveTurn | null>(null)
  const controller = useRef<AbortController | null>(null)
  const mounted = useRef(true)

  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
      controller.current?.abort()
    }
  }, [])

  const update = useCallback((change: (turn: LiveTurn) => LiveTurn) => {
    if (mounted.current) setLive((turn) => (turn ? change(turn) : turn))
  }, [])

  /** The partial answer is saved by the server a moment after the stream ended; wait for it to show up. */
  const adoptSavedPartial = useCallback(async () => {
    const before = qc.getQueryData<ChatAnswer[]>(['history'])?.length ?? 0
    for (let attempt = 0; attempt < 8; attempt++) {
      await wait(200 * (attempt + 1))
      try {
        const history = await qc.fetchQuery({ queryKey: ['history'], queryFn: api.history, staleTime: 0 })
        if (history.length > before) break
      } catch {
        /* keep trying; the live turn stays visible meanwhile */
      }
    }
    if (mounted.current) setLive(null)
  }, [qc])

  const send = useCallback(
    async (question: string) => {
      const q = question.trim()
      if (!q || controller.current) return
      const ctl = new AbortController()
      controller.current = ctl
      setLive({ question: q, text: '', sources: [], phase: 'searching', error: null, stopped: false })

      try {
        for await (const event of api.askStream(q, ctl.signal)) {
          if (event.type === 'sources') {
            update((t) => ({ ...t, sources: event.sources, phase: 'reading' }))
          } else if (event.type === 'token') {
            update((t) => ({ ...t, text: t.text + event.text, phase: 'writing' }))
          } else if (event.type === 'done') {
            qc.setQueryData<ChatAnswer[]>(['history'], (old = []) => [...old, event.message])
            if (mounted.current) setLive(null)
            return
          } else {
            update((t) => ({ ...t, error: new ApiError(0, event.message, event.code) }))
            await adoptSavedPartial()
            return
          }
        }
        // The stream ended without a final event: treat it like a lost connection.
        update((t) => ({ ...t, error: new ApiError(0, 'Anslutningen bröts innan svaret var klart.', 'network') }))
        await adoptSavedPartial()
      } catch (error) {
        if (error instanceof DOMException && error.name === 'AbortError') {
          update((t) => ({ ...t, stopped: true }))
          await adoptSavedPartial()
        } else {
          update((t) => ({ ...t, error: error instanceof ApiError ? error : new ApiError(0, 'Något gick fel.') }))
        }
      } finally {
        controller.current = null
      }
    },
    [qc, update, adoptSavedPartial],
  )

  const stop = useCallback(() => controller.current?.abort(), [])
  /** Removes a failed turn from the screen (it was never saved). */
  const dismiss = useCallback(() => setLive(null), [])

  const busy = live !== null && live.error === null && !live.stopped
  return { live, busy, send, stop, dismiss }
}
