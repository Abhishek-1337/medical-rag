import { useRef, useState } from 'react'
import { streamChat, type ChatEvent, type ChatMessage, type Source, type ChartData } from '../lib/api'
import { Markdown } from './Markdown'
import { Chart } from './Chart'

const SUGGESTIONS = [
  'Summarize the last 12 months',
  'Any threshold crossings?',
  'How should the genetic flags be read here?',
  'What is in the review queue?',
]

function SourceChip({ s }: { s: Source }) {
  const color =
    s.type === 'flag' || s.type === 'queue'
      ? 'border-hosp-amber/50 text-hosp-amber'
      : s.type === 'summary'
        ? 'border-hosp-tealdim/50 text-hosp-teal'
        : 'border-hosp-bluedim/50 text-hosp-blue'
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 font-mono text-[9px] ${color}`} title={s.source}>
      {s.type === 'knowledge' ? 'DOC' : s.type === 'result' ? 'READING' : s.type === 'flag' ? 'FLAG' : 'QUEUE'} · {s.label}
    </span>
  )
}

export function Chat({ patientId, patientName }: { patientId: string; patientName: string }) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [error, setError] = useState('')
  const abortRef = useRef<AbortController | null>(null)

  /** Update the last message in the list (the in-flight assistant reply). */
  const appendToken = (text: string) =>
    setMessages((prev) => {
      const next = [...prev]
      next[next.length - 1] = { ...next[next.length - 1], content: next[next.length - 1].content + text }
      return next
    })

  const setLastSources = (sources: Source[]) =>
    setMessages((prev) => {
      const next = [...prev]
      next[next.length - 1] = { ...next[next.length - 1], sources }
      return next
    })

  const setLastChart = (chart: ChartData) =>
    setMessages((prev) => {
      const next = [...prev]
      next[next.length - 1] = { ...next[next.length - 1], chart }
      return next
    })

  async function send(text: string) {
    const question = text.trim()
    if (!question || streaming) return
    setInput('')
    setError('')
    setMessages((m) => [...m, { role: 'user', content: question }, { role: 'assistant', content: '' }])
    setStreaming(true)

    const controller = new AbortController()
    abortRef.current = controller

    try {
      await streamChat(
        { message: question, patientId, history: messages.slice(-8) },
        (e: ChatEvent) => {
          if (e.event === 'token') appendToken(e.data.text ?? '')
          else if (e.event === 'sources' && e.data.sources) setLastSources(e.data.sources)
          else if (e.event === 'chart' && e.data.chart) setLastChart(e.data.chart)
          else if (e.event === 'error') setError(e.data.message ?? 'chat failed')
        },
        controller.signal,
      )
    } catch (err) {
      if (!(err instanceof DOMException && err.name === 'AbortError')) {
        setError(err instanceof Error ? err.message : String(err))
      }
    } finally {
      abortRef.current = null
      setStreaming(false)
    }
  }

  function stop() {
    abortRef.current?.abort()
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-center gap-2 border-b border-hosp-line bg-hosp-panel px-4 py-2.5 font-mono text-[10px] uppercase tracking-[0.14em] text-hosp-muted">
        <span className="inline-block h-1.5 w-1.5 rounded-full bg-hosp-teal" />
        assistant · scoped to <span className="text-hosp-blue">{patientName}</span>
        {streaming && <span className="ml-auto animate-[hosp-blink_1s_infinite] text-hosp-amber">● streaming</span>}
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto px-4 py-4">
        {messages.length === 0 && (
          <div className="pt-6">
            <p className="text-sm text-hosp-muted">
              Ask about {patientName}'s trends, thresholds, flags, or the review queue. Answers are grounded in the record and clinical knowledge base — never invented.
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  disabled={streaming}
                  className="rounded-full border border-dashed border-hosp-line bg-hosp-panel px-3.5 py-1.5 font-mono text-[10.5px] text-hosp-muted transition-colors hover:border-hosp-blue hover:text-hosp-blue disabled:opacity-40"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) =>
          m.role === 'user' ? (
            <div key={i} className="flex justify-end">
              <div className="max-w-[85%] rounded-2xl rounded-br-md border border-hosp-bluedim/30 bg-hosp-bluetint px-3.5 py-2.5 text-sm text-hosp-text">
                {m.content}
              </div>
            </div>
          ) : (
            <div key={i} className="flex justify-start">
              <div className="max-w-[92%]">
                <div className="card-shadow max-w-[92%] rounded-2xl rounded-bl-md border border-hosp-line bg-hosp-panel px-3.5 py-2.5 text-sm leading-relaxed text-hosp-text">
                  {m.chart && <Chart data={m.chart} />}
                  {m.content ? (
                    <Markdown text={m.content} />
                  ) : streaming && i === messages.length - 1 ? (
                    <span className="font-mono text-hosp-dim">▋</span>
                  ) : null}
                  {streaming && i === messages.length - 1 && m.content && (
                    <span className="ml-0.5 inline-block h-3.5 w-2 animate-[hosp-caret_1s_infinite] bg-hosp-blue align-text-bottom" />
                  )}
                </div>
                {m.sources && m.sources.length > 0 && (
                  <div className="mt-1.5 flex flex-wrap gap-1.5">
                    {m.sources.map((s, j) => (
                      <SourceChip key={j} s={s} />
                    ))}
                  </div>
                )}
              </div>
            </div>
          ),
        )}

        {error && (
          <div className="rounded-xl border border-hosp-red bg-hosp-errbg px-3.5 py-2.5 font-mono text-[11px] text-hosp-errtext">
            {error}
          </div>
        )}
      </div>

      <form
        className="border-t border-hosp-line bg-hosp-panel p-3"
        onSubmit={(e) => {
          e.preventDefault()
          send(input)
        }}
      >
        <div className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about this patient…"
            className="flex-1 rounded-full border border-hosp-line bg-hosp-bg px-4 py-2.5 font-mono text-[12px] text-hosp-text placeholder:text-hosp-dim focus:border-hosp-blue focus:outline-none"
          />
          {streaming ? (
            <button
              type="button"
              onClick={stop}
              className="rounded-full border border-hosp-red bg-hosp-errbg px-5 py-2 font-mono text-[11px] font-semibold uppercase tracking-[0.1em] text-hosp-errtext transition-colors hover:bg-hosp-red hover:text-white"
            >
              Stop
            </button>
          ) : (
            <button
              type="submit"
              disabled={!input.trim()}
              className="rounded-full border border-hosp-blue bg-hosp-blue px-5 py-2 font-mono text-[11px] font-semibold uppercase tracking-[0.1em] text-white transition-colors hover:bg-hosp-bluedim disabled:opacity-40"
            >
              Send
            </button>
          )}
        </div>
      </form>
    </div>
  )
}
