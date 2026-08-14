import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { getPatients, type PatientRow } from '../lib/api'
import { Brand } from '../components/Brand'

export function PatientsList() {
  const [rows, setRows] = useState<PatientRow[]>([])
  const [q, setQ] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    let active = true
    setLoading(true)
    getPatients(q)
      .then((r) => {
        if (active) {
          setRows(r)
          setError('')
        }
      })
      .catch((e) => active && setError(String(e.message ?? e)))
      .finally(() => active && setLoading(false))
    return () => {
      active = false
    }
  }, [q])

  return (
    <div className="min-h-screen">
      <header className="border-b border-hosp-line bg-hosp-panel">
        <div className="mx-auto flex max-w-3xl items-center gap-4 px-6 py-4">
          <Brand tagline="clinical decision support" />
          <span className="ml-auto flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.14em] text-hosp-blue">
            <span className="inline-block h-1.5 w-1.5 animate-[hosp-blink_2.2s_infinite] rounded-full bg-hosp-blue" />
            {loading ? 'loading' : `${rows.length} patients`}
          </span>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-6 py-8">
        <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-hosp-muted">patient search</p>
        <h1 className="mt-2 text-2xl font-semibold text-hosp-text">Pick a chart to ask about</h1>

        <label className="mt-6 block">
          <span className="font-mono text-[9.5px] uppercase tracking-[0.14em] text-hosp-dim">Search by name or member id</span>
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="e.g. Meera or MK-1042"
            className="card-shadow mt-1 w-full rounded-xl border border-hosp-line bg-hosp-panel px-4 py-2.5 font-mono text-[12px] text-hosp-text placeholder:text-hosp-dim focus:border-hosp-blue focus:outline-none"
          />
        </label>

        {error && (
          <div className="mt-4 rounded-xl border border-hosp-red bg-hosp-errbg px-4 py-3 font-mono text-[11px] text-hosp-errtext">
            {error}
          </div>
        )}

        <div className="mt-6 space-y-3">
          {rows.map((p) => (
            <button
              key={p.id}
              onClick={() => navigate(`/patients/${p.id}`)}
              className="card-shadow flex w-full items-center gap-3.5 rounded-xl border border-hosp-line bg-hosp-panel px-4 py-3.5 text-left transition-colors hover:border-hosp-blue"
            >
              <span
                className={`h-11 w-1.5 shrink-0 rounded-full ${p.pendingReview > 0 ? 'bg-hosp-teal' : 'bg-hosp-blue'}`}
              />
              <span className="grid min-w-0 flex-1 gap-0.5">
                <span className="flex items-center gap-2 text-[15px] font-medium text-hosp-text">
                  {p.name}
                  <span className="inline-block h-2.5 w-2.5 shrink-0 rounded-full border border-hosp-dim" />
                </span>
                <span className="font-mono text-[10.5px] text-hosp-muted">
                  {p.memberId} · {p.age}
                  {p.sex === 'Female' ? 'F' : 'M'} · panel {p.latestPanel}
                </span>
              </span>
              {p.pendingReview > 0 && (
                <span className="rounded-full bg-hosp-tealtint px-2.5 py-0.5 font-mono text-[9.5px] font-semibold text-hosp-teal">
                  {p.pendingReview} pending review
                </span>
              )}
              <span className="font-mono text-[9.5px] uppercase tracking-[0.1em] text-hosp-dim">
                {p.summaryStatus.replace(/_/g, ' ')}
              </span>
            </button>
          ))}
          {!loading && rows.length === 0 && (
            <p className="py-10 text-center font-mono text-[11px] text-hosp-dim">no patients match “{q}”</p>
          )}
        </div>
      </main>
    </div>
  )
}
