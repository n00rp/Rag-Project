import { useEffect, useState } from 'react'
import type { ChatAnswer } from '../lib/types'
import { ChatTurn } from './ChatTurn'
import { Sheet } from './ui/Sheet'

interface Recording {
  recordedAt: string
  model: string
  turns: ChatAnswer[]
}

/**
 * A recorded session: real answers (made by scripts/record_demo_session.py) to a fixed set of questions, so that
 * someone can see what the app does while the AI model is offline. Sources show where an answer came from but
 * cannot be opened, because the recording does not come with the documents.
 */
export function DemoSession({ onClose }: { onClose: () => void }) {
  const [recording, setRecording] = useState<Recording | 'missing' | null>(null)

  useEffect(() => {
    let cancelled = false
    fetch('/demo-session.json')
      .then((res) => (res.ok ? (res.json() as Promise<Recording>) : Promise.reject(new Error('missing'))))
      .then((data) => !cancelled && setRecording(data))
      .catch(() => !cancelled && setRecording('missing'))
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <Sheet open onClose={onClose} side="right" title="Inspelad exempelsession" widthClass="w-[min(44rem,100vw)]">
      <div className="h-full overflow-y-auto px-5 py-5">
        {recording === null && <p className="text-sm text-muted">Läser in…</p>}
        {recording === 'missing' && <p className="text-sm text-danger">Det finns ingen inspelad session i den här versionen.</p>}
        {recording && recording !== 'missing' && (
          <>
            <p className="mb-6 rounded-2xl bg-surface-2 p-3.5 text-sm leading-relaxed text-muted">
              Det här är sparade svar, inspelade {new Date(recording.recordedAt).toLocaleDateString('sv-SE')} med modellen{' '}
              <strong className="font-medium text-fg">{recording.model}</strong> mot sex Göteborgsprotokoll. Du kan peka på
              källorna för att se var svaren kommer ifrån, men inte öppna dokumenten.
            </p>
            <div className="flex flex-col gap-7">
              {recording.turns.map((turn) => (
                <ChatTurn key={turn.id} turn={turn} />
              ))}
            </div>
          </>
        )}
      </div>
    </Sheet>
  )
}
