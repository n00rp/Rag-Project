import { useCallback, useState } from 'react'
import { FolderOpen, Moon, Sun, WifiOff } from 'lucide-react'
import { clsx } from 'clsx'
import { ChatView } from './components/ChatView'
import { DocumentPanel } from './components/DocumentPanel'
import { APP_NAME, Logo } from './components/Logo'
import { PdfViewer } from './components/PdfViewer'
import { Sheet } from './components/ui/Sheet'
import { useHealth } from './hooks/queries'
import { useTheme } from './lib/theme'
import type { ViewerTarget } from './lib/types'

function HealthPill() {
  const { data, isError } = useHealth()
  if (!data && !isError) return null

  const aiOnline = !!data?.aiService && !isError
  return (
    <span
      className={clsx(
        'hidden items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium sm:inline-flex',
        aiOnline ? 'bg-ok-soft text-ok' : 'bg-warn-soft text-warn',
      )}
    >
      <span className={clsx('size-1.5 rounded-full', aiOnline ? 'bg-ok' : 'bg-warn')} aria-hidden />
      {aiOnline ? 'AI online' : 'AI offline'}
    </span>
  )
}

function OfflineBanner() {
  const { data, isError } = useHealth()
  if (data?.aiService !== false && !isError) return null

  return (
    <div role="status" className="flex items-center justify-center gap-2 bg-warn-soft px-4 py-2 text-center text-sm text-warn">
      <WifiOff className="size-4 shrink-0" aria-hidden />
      <span>
        {isError
          ? 'Kan inte nå servern just nu.'
          : 'AI-modellen är offline just nu. Du kan bläddra bland dokumenten – frågor fungerar när den är tillbaka.'}
      </span>
    </div>
  )
}

export default function App() {
  const { theme, toggle } = useTheme()
  const [viewer, setViewer] = useState<ViewerTarget | null>(null)
  const [docsOpen, setDocsOpen] = useState(false)
  const closeViewer = useCallback(() => setViewer(null), [])
  const closeDocs = useCallback(() => setDocsOpen(false), [])

  return (
    <div className="flex h-dvh flex-col">
      <header className="flex items-center gap-3 border-b border-line bg-surface px-4 py-2.5">
        <Logo className="size-8" />
        <span className="text-base font-semibold tracking-tight">{APP_NAME}</span>
        <div className="ml-auto flex items-center gap-2">
          <HealthPill />
          <button
            onClick={() => setDocsOpen(true)}
            className="inline-flex items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 text-sm font-medium hover:bg-surface-2 lg:hidden"
          >
            <FolderOpen className="size-4" aria-hidden /> Dokument
          </button>
          <button
            onClick={toggle}
            aria-label={theme === 'dark' ? 'Byt till ljust läge' : 'Byt till mörkt läge'}
            className="rounded-lg p-2 text-muted hover:bg-surface-2 hover:text-fg"
          >
            {theme === 'dark' ? <Sun className="size-5" /> : <Moon className="size-5" />}
          </button>
        </div>
      </header>

      <OfflineBanner />

      <div className="flex min-h-0 flex-1">
        <aside className="hidden w-[22rem] shrink-0 border-r border-line bg-bg lg:block">
          <DocumentPanel onOpen={setViewer} />
        </aside>
        <main className="min-w-0 flex-1">
          <ChatView onOpen={setViewer} />
        </main>
      </div>

      <Sheet open={docsOpen} onClose={closeDocs} side="left" title="Dokument">
        <DocumentPanel
          onOpen={(t) => {
            setDocsOpen(false)
            setViewer(t)
          }}
        />
      </Sheet>
      <PdfViewer target={viewer} onClose={closeViewer} />
    </div>
  )
}
