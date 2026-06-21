import { useEffect, useRef } from 'react'
import type { Message } from '../types'

const VERDICT_LABEL: Record<string, string> = {
  grounded: 'Grounded',
  partially_grounded: 'Partially grounded',
  conflict: 'Conflict',
  refused: "Not in documents",
  unsupported: 'Unsupported',
  unverified: 'Unverified',
}

function renderWithCitations(text: string) {
  const parts = text.split(/(\[\d+\])/g)
  return parts.map((part, i) =>
    /^\[\d+\]$/.test(part) ? (
      <sup key={i} className="cite">
        {part}
      </sup>
    ) : (
      <span key={i}>{part}</span>
    ),
  )
}

export function ConversationView({ messages, partial }: { messages: Message[]; partial: string }) {
  const endRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, partial])

  return (
    <div className="conversation">
      {messages.length === 0 && !partial && (
        <p className="muted center">Upload documents, then press the mic and ask a question.</p>
      )}
      {messages.map((m, i) => (
        <div key={i} className={`bubble ${m.role}`}>
          <div className="bubble-text">{renderWithCitations(m.content)}</div>
          {m.role === 'assistant' && m.verification && (
            <div className={`verdict verdict-${m.verification.verdict}`}>
              {VERDICT_LABEL[m.verification.verdict] || m.verification.verdict}
              {m.verification.conflicts?.length > 0 && (
                <ul className="conflict-list">
                  {m.verification.conflicts.map((c, j) => (
                    <li key={j}>{c}</li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      ))}
      {partial && (
        <div className="bubble user partial">
          <div className="bubble-text">{partial}</div>
        </div>
      )}
      <div ref={endRef} />
    </div>
  )
}
