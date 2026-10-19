import { useId } from 'react'

export const APP_NAME = 'Kommunkoll'

/** A page with a spark: the document, and the answer that lights up inside it. */
export function Logo({ className = 'size-8' }: { className?: string }) {
  const gradient = useId()
  return (
    <svg viewBox="0 0 32 32" className={className} role="img" aria-label={APP_NAME}>
      <defs>
        <linearGradient id={gradient} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" style={{ stopColor: 'var(--accent)' }} />
          <stop offset="1" style={{ stopColor: 'var(--accent-2)' }} />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="9" fill={`url(#${gradient})`} />
      <path d="M10 7h8l5 5v13a1 1 0 0 1-1 1H10a1 1 0 0 1-1-1V8a1 1 0 0 1 1-1z" className="fill-accent-fg" />
      <path d="M18 7v4a1 1 0 0 0 1 1h4z" className="fill-accent-fg" opacity="0.5" />
      <path d="M12.5 17h7M12.5 20h7M12.5 23h3.5" stroke={`url(#${gradient})`} strokeWidth="1.7" strokeLinecap="round" fill="none" />
    </svg>
  )
}
