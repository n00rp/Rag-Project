import { Layers, TriangleAlert } from 'lucide-react'
import type { Support } from '../lib/types'

interface Props {
  support?: Support
  broad?: boolean
}

function Badge({ icon, children, title }: { icon: React.ReactNode; children: React.ReactNode; title: string }) {
  return (
    <span title={title} className="inline-flex items-center gap-1.5 rounded-full bg-warn-soft px-2.5 py-1 text-xs font-medium text-warn">
      {icon}
      {children}
    </span>
  )
}

/** Tells the reader when an answer is not the whole truth: only partly supported, or built from a sample of excerpts. */
export function SupportNotice({ support, broad }: Props) {
  if (support !== 'delvis' && !broad) return null

  return (
    <div className="mb-3 flex flex-wrap gap-2">
      {support === 'delvis' && (
        <Badge
          icon={<TriangleAlert className="size-3.5" aria-hidden />}
          title="Dokumenten handlar om ämnet men svarar inte på hela frågan, eller motsäger ett antagande i den."
        >
          Delvis stöd i dokumenten
        </Badge>
      )}
      {broad && (
        <Badge
          icon={<Layers className="size-3.5" aria-hidden />}
          title="Frågan kräver en genomgång av många ärenden. Svaret bygger på de mest relevanta utdragen, inte på hela dokumenten."
        >
          Översikt av de mest relevanta utdragen, kan vara ofullständig
        </Badge>
      )}
    </div>
  )
}
