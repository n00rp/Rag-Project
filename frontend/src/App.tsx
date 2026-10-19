import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from 'react'
import { FolderOpen, Moon, Search, Sun, WifiOff } from 'lucide-react'
import { clsx } from 'clsx'
import { ChatView } from './components/ChatView'
import { CommandPalette, type Command } from './components/CommandPalette'
import { DemoSession } from './components/DemoSession'
import { DocumentPanel } from './components/DocumentPanel'
import { APP_NAME, Logo } from './components/Logo'
import { Sheet } from './components/ui/Sheet'
import { useClearHistory, useHealth } from './hooks/queries'
import { useMediaQuery } from './hooks/useMediaQuery'
import { useTheme } from './lib/theme'
import type { ViewerTarget } from './lib/types'

// pdf.js is large and only needed once a source is opened.
const PdfViewer = lazy(() => import('./components/PdfViewer').then((m) => ({ default: m.PdfViewer })))

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

function OfflineBanner({ onShowDemo }: { onShowDemo: () => void }) {
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
      <button onClick={onShowDemo} className="shrink-0 font-semibold underline underline-offset-2 hover:no-underline">
        Se en inspelad exempelsession
      </button>
    </div>
  )
}

export default function App() {
  const { theme, toggle } = useTheme()
  const [viewer, setViewer] = useState<ViewerTarget | null>(null)
  const [docsOpen, setDocsOpen] = useState(false)
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [demoOpen, setDemoOpen] = useState(false)
  const clearHistory = useClearHistory()
  // Wide screens show the source next to the chat; the panel for the documents is always visible from `lg`.
  const wide = useMediaQuery('(min-width: 1280px)')
  const sidebarVisible = useMediaQuery('(min-width: 1024px)')
  const closeViewer = useCallback(() => setViewer(null), [])
  const closeDocs = useCallback(() => setDocsOpen(false), [])
  const closePalette = useCallback(() => setPaletteOpen(false), [])
  const closeDemo = useCallback(() => setDemoOpen(false), [])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setPaletteOpen((open) => !open)
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [])

  const commands = useMemo<Command[]>(
    () => [
      { id: 'new', label: 'Ny konversation', run: () => clearHistory.mutate() },
      { id: 'theme', label: theme === 'dark' ? 'Byt till ljust läge' : 'Byt till mörkt läge', run: toggle },
      { id: 'demo', label: 'Visa inspelad exempelsession', run: () => setDemoOpen(true) },
      ...(sidebarVisible ? [] : [{ id: 'docs', label: 'Visa dokument', run: () => setDocsOpen(true) }]),
      ...(viewer ? [{ id: 'close-source', label: 'Stäng källvisaren', hint: 'Esc', run: closeViewer }] : []),
    ],
    [clearHistory, theme, toggle, sidebarVisible, viewer, closeViewer],
  )

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
            onClick={() => setPaletteOpen(true)}
            aria-label="Öppna kommandon (Ctrl+K)"
            title="Kommandon (Ctrl+K)"
            className="hidden items-center gap-2 rounded-lg border border-line px-2.5 py-1.5 text-xs text-muted hover:bg-surface-2 hover:text-fg sm:inline-flex"
          >
            <Search className="size-3.5" aria-hidden />
            <kbd className="font-sans">Ctrl K</kbd>
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

      <OfflineBanner onShowDemo={() => setDemoOpen(true)} />

      <div className="flex min-h-0 flex-1">
        <aside className="hidden w-[22rem] shrink-0 border-r border-line bg-bg lg:block">
          <DocumentPanel onOpen={setViewer} />
        </aside>
        <main className="min-w-0 flex-1">
          <ChatView onOpen={setViewer} />
        </main>
        {viewer && wide && (
          <aside className="w-[min(44rem,42vw)] shrink-0 border-l border-line">
            <Suspense fallback={null}>
              <PdfViewer target={viewer} onClose={closeViewer} docked />
            </Suspense>
          </aside>
        )}
      </div>

      <Sheet open={docsOpen} onClose={closeDocs} side="left" title="Dokument">
        <DocumentPanel
          onOpen={(t) => {
            setDocsOpen(false)
            setViewer(t)
          }}
        />
      </Sheet>
      {viewer && !wide && (
        <Suspense fallback={null}>
          <PdfViewer target={viewer} onClose={closeViewer} />
        </Suspense>
      )}
      {demoOpen && <DemoSession onClose={closeDemo} />}
      {paletteOpen && <CommandPalette commands={commands} onClose={closePalette} />}
    </div>
  )
}
