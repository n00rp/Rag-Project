import { useEffect, useRef, useState } from 'react'
import { getDocument, GlobalWorkerOptions, Util } from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import { findHighlightedItems } from '../lib/highlight'

GlobalWorkerOptions.workerSrc = workerUrl

interface Box {
  left: number
  top: number
  width: number
  height: number
}

interface Props {
  url: string
  page: number
  /** Excerpt to highlight on the page. */
  snippet?: string
  onPageCount?: (pages: number) => void
  /** Called when the PDF cannot be rendered, so the caller can fall back to the browser's viewer. */
  onError: () => void
}

/** One PDF page drawn on a canvas, with the cited excerpt highlighted on top. */
export function PdfPage({ url, page, snippet, onPageCount, onError }: Props) {
  const container = useRef<HTMLDivElement>(null)
  const canvas = useRef<HTMLCanvasElement>(null)
  const [boxes, setBoxes] = useState<Box[]>([])
  const [size, setSize] = useState({ width: 0, height: 0 })
  const [found, setFound] = useState<boolean | null>(null)

  useEffect(() => {
    let cancelled = false
    const task = getDocument({ url })

    async function draw() {
      const pdf = await task.promise
      if (cancelled) return
      onPageCount?.(pdf.numPages)
      const pdfPage = await pdf.getPage(Math.min(Math.max(page, 1), pdf.numPages))
      const available = container.current?.clientWidth || 640
      const scale = available / pdfPage.getViewport({ scale: 1 }).width
      const viewport = pdfPage.getViewport({ scale })
      const ratio = window.devicePixelRatio || 1

      const el = canvas.current
      if (!el || cancelled) return
      el.width = Math.floor(viewport.width * ratio)
      el.height = Math.floor(viewport.height * ratio)
      setSize({ width: viewport.width, height: viewport.height })
      await pdfPage.render({
        canvas: el,
        viewport,
        transform: ratio === 1 ? undefined : [ratio, 0, 0, ratio, 0, 0],
      }).promise
      if (cancelled) return

      const content = await pdfPage.getTextContent()
      const items = content.items.filter((i) => 'str' in i)
      const covered = snippet ? findHighlightedItems(items.map((i) => i.str), snippet) : new Set<number>()
      setFound(snippet ? covered.size > 0 : null)
      setBoxes(
        [...covered].map((index) => {
          const item = items[index]
          const [, , , d, x, y] = Util.transform(viewport.transform, item.transform)
          const height = Math.abs(d)
          return { left: x, top: y - height * 0.85, width: item.width * scale, height: height * 1.15 }
        }),
      )
    }

    draw().catch(() => !cancelled && onError())
    return () => {
      cancelled = true
      task.destroy()
    }
    // onPageCount/onError are not memoised by callers; the page, file and excerpt decide what is drawn.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, page, snippet])

  return (
    <div ref={container} className="w-full">
      <div className="relative mx-auto bg-white shadow-sm" style={{ width: size.width || '100%', height: size.height || undefined }}>
        <canvas ref={canvas} style={{ width: size.width || '100%', height: size.height || undefined }} aria-label={`PDF-sida ${page}`} role="img" />
        {boxes.map((b, i) => (
          <div
            key={i}
            aria-hidden
            className="pointer-events-none absolute rounded-sm bg-yellow-300/45 mix-blend-multiply"
            style={{ left: b.left, top: b.top, width: b.width, height: b.height }}
          />
        ))}
      </div>
      {found === false && (
        <p className="mt-2 text-center text-xs text-muted">Utdraget gick inte att markera på sidan, men sidan visas.</p>
      )}
    </div>
  )
}
