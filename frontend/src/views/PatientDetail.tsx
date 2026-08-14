import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router'
import { getPatient, type PatientDetail } from '../lib/api'
import { Chat } from '../components/Chat'
import { Brand } from '../components/Brand'
import { RecordsTable } from '../components/RecordsTable'

function latestByType(p: PatientDetail): { type: string; latest: number; first: number; unit: string }[] {
  return Object.entries(p.biomarkers).map(([type, readings]) => {
    const sorted = [...readings].sort((a, b) => a.date.localeCompare(b.date))
    const first = sorted[0].value
    const latest = sorted[sorted.length - 1].value
    const unit = type === 'HbA1c' ? '%' : 'mg/dL'
    return { type, latest, first, unit }
  })
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

function fmtDate(iso: string): string {
  const [y, m] = iso.split('-')
  return `${MONTHS[Number(m) - 1]} ${y}`
}

export function PatientDetail() {
  const { id } = useParams<{ id: string }>()
  const [patient, setPatient] = useState<PatientDetail | null>(null)
  const [error, setError] = useState('')
  const [tab, setTab] = useState<'records' | 'assistant'>('records')
  const navigate = useNavigate()

  useEffect(() => {
    if (!id) return
    getPatient(id)
      .then(setPatient)
      .catch((e) => setError(String(e.message ?? e)))
  }, [id])

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center px-6">
        <div className="card-shadow rounded-xl border border-hosp-red bg-hosp-errbg px-5 py-4 font-mono text-[12px] text-hosp-errtext">
          {error} ·{' '}
          <button className="underline" onClick={() => navigate('/')}>
            back to patients
          </button>
        </div>
      </div>
    )
  }

  if (!patient) {
    return <div className="flex min-h-screen items-center justify-center font-mono text-[11px] text-hosp-dim">loading…</div>
  }

  const latest = latestByType(patient)
  const activeSummary = patient.summaries[patient.summaries.length - 1]
  const readingCount = Object.values(patient.biomarkers).reduce((n, rs) => n + rs.length, 0)

  return (
    <div className="flex h-screen min-h-0 flex-col">
      <header className="flex flex-wrap items-center gap-3 border-b border-hosp-line bg-hosp-panel px-5 py-3">
        <button
          onClick={() => navigate('/')}
          className="rounded-full border border-hosp-line px-3 py-1 font-mono text-[11px] uppercase tracking-[0.1em] text-hosp-muted transition-colors hover:border-hosp-blue hover:text-hosp-blue"
        >
          ← patients
        </button>
        <Brand tagline="chart" />
        <span className="font-mono text-[9px] uppercase tracking-[0.1em] text-hosp-dim">· {patient.memberId}</span>
        {activeSummary && (
          <span
            className={`ml-auto rounded-full px-2.5 py-1 font-mono text-[9.5px] uppercase tracking-[0.12em] ${
              activeSummary.status === 'pending_review'
                ? 'bg-hosp-ambertint text-hosp-amber'
                : 'bg-hosp-tealtint text-hosp-teal'
            }`}
          >
            {activeSummary.status.replace(/_/g, ' ')}
          </span>
        )}
      </header>

      <div className="grid min-h-0 flex-1 lg:grid-cols-[330px_1fr]">
        <aside className="overflow-y-auto border-b border-hosp-line bg-hosp-panel p-4 lg:border-b-0 lg:border-r">
          <div className="flex items-start gap-3">
            <div>
              <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight text-hosp-text">
                {patient.name}
                <span className="inline-block h-2.5 w-2.5 rounded-full border border-hosp-dim" />
              </h1>
              <p className="mt-0.5 font-mono text-[10.5px] text-hosp-muted">
                {patient.memberId} · {patient.age}
                {patient.sex === 'Female' ? 'F' : 'M'} · {readingCount} readings
              </p>
            </div>
          </div>

          {patient.geneticFlags.length > 0 && (
            <div className="mt-4 rounded-xl border border-hosp-amber/50 border-l-[3px] bg-hosp-ambertint px-3 py-2.5">
              <p className="text-[12.5px] font-medium text-hosp-amber">▲ {patient.geneticFlags.join(' · ')}</p>
              <p className="mt-0.5 font-mono text-[9.5px] text-hosp-amber/80">applies extra weight to trend interpretation</p>
            </div>
          )}

          <div className="mt-4 grid grid-cols-2 gap-2">
            {latest.map((v) => {
              const pct = v.first === 0 ? 0 : ((v.latest - v.first) / v.first) * 100
              const dir = pct > 0.5 ? '▲' : pct < -0.5 ? '▼' : '→'
              const color = dir === '→' ? 'text-hosp-dim' : 'text-hosp-amber'
              return (
                <div key={v.type} className="card-shadow rounded-xl border border-hosp-line bg-hosp-panel px-3 py-2.5">
                  <p className="font-mono text-[9px] uppercase tracking-[0.14em] text-hosp-muted">{v.type}</p>
                  <p className="mt-0.5 text-xl font-semibold tabular-nums text-hosp-text">
                    {v.unit === '%' ? v.latest.toFixed(1) : v.latest}
                    <span className="ml-1 font-mono text-[9.5px] font-normal text-hosp-dim">{v.unit}</span>
                  </p>
                  <p className={`mt-0.5 font-mono text-[9.5px] ${color}`}>{dir} {Math.abs(pct).toFixed(1)}% · 12-mo</p>
                </div>
              )
            })}
          </div>

          {activeSummary && (
            <div className="card-shadow mt-4 rounded-xl border border-hosp-line bg-hosp-panel px-3.5 py-3">
              <p className="flex items-center justify-between font-mono text-[9.5px] uppercase tracking-[0.14em] text-hosp-muted">
                latest summary
                <span
                  className={`rounded-full px-2 py-0.5 text-[9px] ${
                    activeSummary.status === 'pending_review'
                      ? 'bg-hosp-ambertint text-hosp-amber'
                      : 'bg-hosp-tealtint text-hosp-teal'
                  }`}
                >
                  {activeSummary.status.replace(/_/g, ' ')}
                </span>
              </p>
              <p className="mt-2 line-clamp-6 text-[12.5px] leading-relaxed text-hosp-muted">{activeSummary.generatedText}</p>
            </div>
          )}

          {patient.biomarkers.LDL && (
            <p className="mt-4 font-mono text-[9.5px] text-hosp-dim">
              panel span · {fmtDate(patient.biomarkers.LDL[0].date)} →{' '}
              {fmtDate(patient.biomarkers.LDL[patient.biomarkers.LDL.length - 1].date)}
            </p>
          )}
        </aside>

        <main className="flex min-h-0 flex-col">
          <div className="flex border-b border-hosp-line bg-hosp-panel px-4 pt-2">
            <div className="flex gap-1 rounded-full bg-hosp-panel2 p-1">
              {(
                [
                  ['records', 'Vitals & records'],
                  ['assistant', 'Assistant'],
                ] as const
              ).map(([key, label]) => (
                <button
                  key={key}
                  onClick={() => setTab(key)}
                  className={`rounded-full px-4 py-1.5 font-mono text-[10px] uppercase tracking-[0.1em] transition-colors ${
                    tab === key ? 'card-shadow bg-hosp-panel font-semibold text-hosp-blue' : 'text-hosp-muted hover:text-hosp-text'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
          {tab === 'records' ? (
            <RecordsTable biomarkers={patient.biomarkers} />
          ) : (
            <Chat patientId={patient.id} patientName={patient.name} />
          )}
        </main>
      </div>
    </div>
  )
}
