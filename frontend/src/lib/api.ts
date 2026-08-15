export interface PatientRow {
  id: string
  name: string
  memberId: string
  age: number
  sex: string
  latestPanel: string
  pendingReview: number
  summaryStatus: string
}

export interface Reading {
  date: string
  value: number
}

export interface SummaryDoc {
  status: string
  generatedText: string
  createdAt?: string
  reviewedBy?: string
  reviewedAt?: string
}

export interface PatientDetail {
  id: string
  name: string
  memberId: string
  age: number
  sex: string
  geneticFlags: string[]
  biomarkers: Record<string, Reading[]>
  summaries: SummaryDoc[]
}

export interface Source {
  type: 'knowledge' | 'result' | 'flag' | 'summary' | 'queue'
  label: string
  source?: string
}

export interface ChartPoint {
  date: string
  value: number
}

export interface ChartSeries {
  name: string
  unit: string
  points: ChartPoint[]
}

export interface ChartData {
  title: string
  series: ChartSeries[]
  thresholds: { value: number; label: string }[]
  note?: string
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  sources?: Source[]
  chart?: ChartData
}

export interface ChatEvent {
  event: 'token' | 'sources' | 'chart' | 'done' | 'error'
  data: { text?: string; sources?: Source[]; chart?: ChartData; message?: string }
}

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

function api(path: string): string {
  return `${API_BASE}${path}`
}

export async function getPatients(q?: string): Promise<PatientRow[]> {
  const url = q && q.trim() ? api(`/api/patients?q=${encodeURIComponent(q)}`) : api('/api/patients')
  const res = await fetch(url)
  if (!res.ok) throw new Error(`patients request failed (${res.status})`)
  return res.json()
}

export async function getPatient(id: string): Promise<PatientDetail> {
  const res = await fetch(api(`/api/patients/${id}`))
  if (!res.ok) throw new Error(`patient request failed (${res.status})`)
  return res.json()
}

export async function streamChat(
  body: { message: string; patientId: string | null; history: ChatMessage[] },
  onEvent: (e: ChatEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(api('/api/chat'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })
  if (!res.ok) {
    const json = await res.json().catch(() => ({}))
    throw new Error(json.error ?? `chat failed (${res.status})`)
  }
  if (!res.body) throw new Error('no response body')

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n')
    let idx: number
    while ((idx = buf.indexOf('\n\n')) !== -1) {
      const raw = buf.slice(0, idx)
      buf = buf.slice(idx + 2)
      const event = raw.match(/^event: (.+)$/m)?.[1]
      const data = raw.match(/^data: (.+)$/m)?.[1]
      if (event && data) {
        onEvent({ event: event as ChatEvent['event'], data: JSON.parse(data) })
      }
    }
  }
}
