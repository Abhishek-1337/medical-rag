import { useMemo, useState } from 'react'
import type { Reading } from '../lib/api'

interface Row {
  id: string
  date: string
  type: string
  value: number
  unit: string
  prev: number | null
}

const TYPE_DOT: Record<string, string> = { LDL: 'bg-hosp-blue', HbA1c: 'bg-hosp-amber', HDL: 'bg-hosp-teal' }
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

function fmtDate(iso: string): string {
  const [y, m, d] = iso.split('-')
  return `${d} ${MONTHS[Number(m) - 1]} ${y}`
}

function isGoodChange(type: string, delta: number): boolean {
  if (type === 'HDL') return delta > 0
  return delta < 0
}

function thresholdBadge(type: string, value: number): { label: string; tone: 'amber' | 'red' } | null {
  if (type === 'LDL' && value >= 160) return { label: 'high', tone: 'amber' }
  if (type === 'HbA1c' && value >= 6.5) return { label: 'diabetes range', tone: 'red' }
  if (type === 'HbA1c' && value >= 5.7) return { label: 'prediabetes', tone: 'amber' }
  if (type === 'HDL' && value < 40) return { label: 'low', tone: 'amber' }
  return null
}

export function RecordsTable({ biomarkers }: { biomarkers: Record<string, Reading[]> }) {
  const [typeFilter, setTypeFilter] = useState<'all' | string>('all')
  const [yearFilter, setYearFilter] = useState<'all' | string>('all')

  const types = useMemo(() => Object.keys(biomarkers).sort(), [biomarkers])
  const years = useMemo(() => {
    const set = new Set<string>()
    for (const readings of Object.values(biomarkers)) for (const r of readings) set.add(r.date.slice(0, 4))
    return [...set].sort().reverse()
  }, [biomarkers])

  const rows: Row[] = useMemo(() => {
    const flat: Row[] = []
    for (const type of types) {
      const sorted = [...biomarkers[type]].sort((a, b) => a.date.localeCompare(b.date))
      let prev: number | null = null
      for (const r of sorted) {
        flat.push({ id: `${type}-${r.date}`, date: r.date, type, value: r.value, unit: type === 'HbA1c' ? '%' : 'mg/dL', prev })
        prev = r.value
      }
    }
    return flat.sort((a, b) => b.date.localeCompare(a.date) || a.type.localeCompare(b.type))
  }, [biomarkers, types])

  const filtered = useMemo(
    () => rows.filter((r) => (typeFilter === 'all' || r.type === typeFilter) && (yearFilter === 'all' || r.date.startsWith(yearFilter))),
    [rows, typeFilter, yearFilter],
  )

  const fmtVal = (v: number, unit: string) => (unit === '%' ? v.toFixed(1) : String(Math.round(v)))

  return (
    <div className="flex min-h-0 flex-1 flex-col px-5 py-4">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex gap-1 rounded-full bg-hosp-panel2 p-1">
          {['all', ...types].map((t) => (
            <button
              key={t}
              onClick={() => setTypeFilter(t)}
              className={`rounded-full px-3 py-1 font-mono text-[10px] uppercase tracking-[0.08em] transition-colors ${
                typeFilter === t ? 'card-shadow bg-hosp-panel font-semibold text-hosp-blue' : 'text-hosp-muted hover:text-hosp-text'
              }`}
            >
              {t === 'all' ? 'All' : t}
            </button>
          ))}
        </div>
        <label className="ml-auto flex items-center gap-2">
          <span className="font-mono text-[9.5px] uppercase tracking-[0.14em] text-hosp-dim">Year</span>
          <select
            value={yearFilter}
            onChange={(e) => setYearFilter(e.target.value)}
            className="rounded-full border border-hosp-line bg-hosp-panel px-3 py-1 font-mono text-[11px] text-hosp-text focus:border-hosp-blue focus:outline-none"
          >
            <option value="all">All years</option>
            {years.map((y) => (
              <option key={y} value={y}>
                {y}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="card-shadow mt-3 flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-hosp-line bg-hosp-panel">
        <div className="min-h-0 flex-1 overflow-y-auto">
          <table className="w-full border-collapse text-left text-[13px]">
            <thead>
              <tr className="sticky top-0 z-10 bg-hosp-panel2 font-mono text-[9.5px] uppercase tracking-[0.12em] text-hosp-muted shadow-[0_1px_0_var(--color-hosp-linesoft)]">
                <th className="px-4 py-2.5 pr-3 font-medium">Date</th>
                <th className="px-3 py-2.5 pr-3 font-medium">Biomarker</th>
                <th className="px-3 py-2.5 pr-3 text-right font-medium">Value</th>
                <th className="px-3 py-2.5 pr-3 text-right font-medium">Δ vs previous</th>
                <th className="px-3 py-2.5 pr-4 font-medium">Note</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((r) => {
                const badge = thresholdBadge(r.type, r.value)
                const delta = r.prev === null ? null : r.value - r.prev
                const tint = badge ? (badge.tone === 'red' ? 'bg-hosp-errbg/40' : 'bg-hosp-ambertint/40') : ''
                return (
                  <tr key={r.id} className={`border-t border-hosp-linesoft transition-colors hover:bg-hosp-panel2/70 ${tint}`}>
                    <td className="whitespace-nowrap px-4 py-2.5 pr-3 font-mono text-[11px] text-hosp-muted">{fmtDate(r.date)}</td>
                    <td className="px-3 py-2.5 pr-3">
                      <span className="flex items-center gap-1.5 font-medium text-hosp-text">
                        <span className={`h-1.5 w-1.5 rounded-full ${TYPE_DOT[r.type] ?? 'bg-hosp-dim'}`} />
                        {r.type}
                      </span>
                    </td>
                    <td className="px-3 py-2.5 pr-3 text-right font-mono tabular-nums">
                      <span className={badge?.tone === 'red' ? 'font-semibold text-hosp-errtext' : badge ? 'font-semibold text-hosp-amber' : 'text-hosp-text'}>
                        {fmtVal(r.value, r.unit)}
                      </span>
                      <span className="ml-1 text-[10px] text-hosp-dim">{r.unit}</span>
                    </td>
                    <td className="px-3 py-2.5 pr-3 text-right font-mono text-[11px]">
                      {delta === null ? (
                        <span className="text-hosp-dim">—</span>
                      ) : (
                        <span className={isGoodChange(r.type, delta) ? 'text-hosp-teal' : 'text-hosp-amber'}>
                          {delta > 0 ? '▲ +' : '▼ '}
                          {fmtVal(Math.abs(delta), r.unit)}
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-2.5 pr-4">
                      {badge && (
                        <span
                          className={`rounded-full px-2 py-0.5 font-mono text-[9px] font-semibold ${
                            badge.tone === 'red' ? 'bg-hosp-errbg text-hosp-errtext' : 'bg-hosp-ambertint text-hosp-amber'
                          }`}
                        >
                          {badge.label}
                        </span>
                      )}
                      {!badge && delta === null && <span className="font-mono text-[9px] text-hosp-dim">baseline</span>}
                    </td>
                  </tr>
                )
              })}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-12 text-center font-mono text-[11px] text-hosp-dim">
                    no readings match these filters
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <div className="border-t border-hosp-linesoft px-4 py-2 font-mono text-[10px] text-hosp-dim">
          {filtered.length} of {rows.length} readings · newest first
        </div>
      </div>
    </div>
  )
}
