import { useMemo } from 'react'
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { ChartData } from '../lib/api'

const SERIES_STROKE: Record<string, string> = {
  LDL: 'var(--color-hosp-blue)',
  HbA1c: 'var(--color-hosp-amber)',
  HDL: 'var(--color-hosp-teal)',
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

function fmtDate(iso: string): string {
  const [y, m] = iso.split('-')
  return `${MONTHS[Number(m) - 1]} ${y.slice(2)}`
}

function TooltipBody({
  active,
  payload,
  label,
}: {
  active?: boolean
  payload?: { dataKey?: string; value?: number }[]
  label?: string | number
}) {
  if (!active || !payload || payload.length === 0) return null
  return (
    <div className="rounded-lg border border-hosp-line bg-hosp-panel px-3 py-2 font-mono text-[10.5px] shadow-lg">
      <p className="mb-1 uppercase tracking-[0.1em] text-hosp-dim">{label}</p>
      {payload.map((p) => (
        <p key={String(p.dataKey)} className="text-hosp-text">
          {p.dataKey}: <span className="font-semibold">{p.value}</span>
        </p>
      ))}
    </div>
  )
}

export function Chart({ data }: { data: ChartData }) {
  const points = useMemo(
    () =>
      data.series[0].points.map((_, i) => {
        const row: Record<string, string | number> = { date: data.series[0].points[i].date }
        for (const s of data.series) {
          row[s.name] = s.points[i]?.value ?? null
        }
        return row
      }),
    [data],
  )

  return (
    <div className="w-full">
      <p className="mb-1 px-1 font-mono text-[9.5px] uppercase tracking-[0.14em] text-hosp-muted">{data.title}</p>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 px-1">
        {data.series.map((s) => (
          <span key={s.name} className="flex items-center gap-1.5 font-mono text-[9.5px] uppercase tracking-[0.1em] text-hosp-muted">
            <span className="inline-block h-[3px] w-4 rounded-full" style={{ background: SERIES_STROKE[s.name] ?? 'var(--color-hosp-dim)' }} />
            {s.name} · {s.unit}
          </span>
        ))}
        {data.thresholds.map((t) => (
          <span key={t.label} className="flex items-center gap-1.5 font-mono text-[9.5px] uppercase tracking-[0.1em] text-hosp-dim">
            <span className="inline-block w-4 border-t border-dashed border-hosp-dim" />
            {t.label}
          </span>
        ))}
      </div>
      <div className="mt-1 h-44 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={points} margin={{ top: 6, right: 8, bottom: 0, left: -18 }}>
            <CartesianGrid stroke="var(--color-hosp-linesoft)" strokeDasharray="2 4" vertical={false} />
            <XAxis
              dataKey="date"
              tickFormatter={fmtDate}
              tick={{ fill: 'var(--color-hosp-dim)', fontSize: 9, fontFamily: 'IBM Plex Mono' }}
              axisLine={{ stroke: 'var(--color-hosp-line)' }}
              tickLine={false}
              interval="preserveStartEnd"
              minTickGap={28}
            />
            <YAxis
              tick={{ fill: 'var(--color-hosp-dim)', fontSize: 9, fontFamily: 'IBM Plex Mono' }}
              axisLine={false}
              tickLine={false}
              domain={['auto', 'auto']}
              width={44}
            />
            <Tooltip content={<TooltipBody />} cursor={{ stroke: 'var(--color-hosp-dim)', strokeDasharray: '2 4' }} />
            {data.thresholds.map((t) => (
              <ReferenceLine
                key={t.label}
                y={t.value}
                stroke="var(--color-hosp-amber)"
                strokeDasharray="4 4"
                strokeOpacity={0.7}
                label={{ value: t.label, position: 'insideTopRight', fill: 'var(--color-hosp-dim)', fontSize: 8.5 }}
              />
            ))}
            {data.series.map((s) => (
              <Line
                key={s.name}
                type="monotone"
                dataKey={s.name}
                stroke={SERIES_STROKE[s.name] ?? 'var(--color-hosp-blue)'}
                strokeWidth={1.8}
                dot={{ r: 2, fill: SERIES_STROKE[s.name] ?? 'var(--color-hosp-blue)', strokeWidth: 0 }}
                activeDot={{ r: 3.5 }}
                connectNulls
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
