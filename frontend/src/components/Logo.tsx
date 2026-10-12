export const APP_NAME = 'Kommunkoll'

export function Logo({ className = 'size-8' }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} role="img" aria-label={APP_NAME}>
      <rect width="32" height="32" rx="8" className="fill-accent" />
      <path d="M10 7h8l5 5v13a1 1 0 0 1-1 1H10a1 1 0 0 1-1-1V8a1 1 0 0 1 1-1z" className="fill-accent-fg" />
      <path d="M18 7v4a1 1 0 0 0 1 1h4z" className="fill-accent-fg" opacity="0.55" />
      <path
        d="M12.5 17h7M12.5 20h7M12.5 23h4"
        className="stroke-accent"
        strokeWidth="1.6"
        strokeLinecap="round"
        fill="none"
      />
    </svg>
  )
}
