import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

const TABLE_HEAD = 'border-b border-hosp-line px-2.5 py-1.5 text-left font-mono text-[9.5px] font-semibold uppercase tracking-[0.08em] text-hosp-muted'
const TABLE_CELL = 'border-b border-hosp-linesoft px-2.5 py-1.5 font-mono text-[11.5px] text-hosp-text'

export function Markdown({ text }: { text: string }) {
  return (
    <div className="markdown-body">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => <div className="mb-1 font-mono text-[10px] font-semibold uppercase tracking-[0.14em] text-hosp-blue">{children}</div>,
          h2: ({ children }) => <div className="mb-1 font-mono text-[10px] font-semibold uppercase tracking-[0.14em] text-hosp-blue">{children}</div>,
          h3: ({ children }) => <div className="mb-1 font-mono text-[10px] font-semibold uppercase tracking-[0.14em] text-hosp-blue">{children}</div>,
          strong: ({ children }) => <span className="font-semibold text-hosp-text">{children}</span>,
          ul: ({ children }) => <ul className="my-1.5 space-y-1 pl-4">{children}</ul>,
          ol: ({ children }) => <ol className="my-1.5 list-decimal space-y-1 pl-4">{children}</ol>,
          li: ({ children }) => <li className="leading-relaxed marker:text-hosp-blue">{children}</li>,
          p: ({ children }) => <p className="my-1.5 leading-relaxed">{children}</p>,
          table: ({ children }) => (
            <div className="my-2 overflow-x-auto rounded-lg border border-hosp-line">
              <table className="w-full min-w-[280px] border-collapse text-sm">{children}</table>
            </div>
          ),
          thead: ({ children }) => <thead>{children}</thead>,
          tbody: ({ children }) => <tbody>{children}</tbody>,
          tr: ({ children }) => <tr>{children}</tr>,
          th: ({ children }) => <th className={TABLE_HEAD}>{children}</th>,
          td: ({ children }) => <td className={TABLE_CELL}>{children}</td>,
          hr: () => <div className="my-2 border-t border-hosp-linesoft" />,
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  )
}
