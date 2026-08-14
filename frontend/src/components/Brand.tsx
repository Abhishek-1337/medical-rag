export function Ecg({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 120 24" className={className} aria-hidden="true">
      <polyline
        className="ecg"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinejoin="round"
        strokeLinecap="round"
        points="0,12 8,12 12,12 15,5 18,12 26,12 30,12 33,7 36,12 44,12 48,12 51,4 54,12 62,12 66,12 69,8 72,12 80,12 84,12 87,5 90,12 98,12 102,12 105,7 108,12 116,12 120,12"
      />
    </svg>
  )
}

export function Brand({ tagline }: { tagline: string }) {
  return (
    <div className="flex items-center gap-3">
      <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-hosp-blue text-white card-shadow">
        <Ecg className="h-5 w-7" />
      </span>
      <div className="leading-tight">
        <p className="text-[15px] font-semibold tracking-tight text-hosp-text">Baseline Assist</p>
        <p className="font-mono text-[8.5px] uppercase tracking-[0.14em] text-hosp-muted">{tagline}</p>
      </div>
    </div>
  )
}
