export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} kB`
  return `${(bytes / (1024 * 1024)).toFixed(1).replace('.', ',')} MB`
}

export function pluralize(n: number, singular: string, plural: string): string {
  return `${n} ${n === 1 ? singular : plural}`
}

const timeFormat = new Intl.DateTimeFormat('sv-SE', { hour: '2-digit', minute: '2-digit' })
const dateFormat = new Intl.DateTimeFormat('sv-SE', { day: 'numeric', month: 'short' })

export function formatTimestamp(iso: string, now = new Date()): string {
  const d = new Date(iso)
  return d.toDateString() === now.toDateString() ? timeFormat.format(d) : dateFormat.format(d)
}

export const MAX_UPLOAD_BYTES = 25 * 1024 * 1024
