import { useEffect, useRef } from 'react'
import type { Message } from '../types'

const STAGE_LABEL: Record<string, string> = {
  thinking: 'Thinking',
  rewriting: 'Understanding your question',
  searching: 'Searching the documents',
  reading: 'Reading the sources',
  verifying: 'Checking the answer',
  answering: 'Answering',
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

export function ConversationView({
  messages,
  partial,
  stage,
}: {
  messages: Message[]
  partial: string
  stage: string
}) {
  const endRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, partial, stage])

  // Show an animated indicator while a question is in flight but no answer text
  // has streamed yet, so the app never looks frozen during the search/verify.
  const last = messages[messages.length - 1]
  const awaitingAnswer =
    stage !== 'idle' && stage !== 'answering' && (!last || last.role === 'user')

  return (
    <div className="conversation">
      {messages.length === 0 && !partial && (
        <p className="muted center">Upload documents, then press the mic and ask a question.</p>
      )}
      {messages.map((m, i) => {
        const sources =
          m.role === 'assistant' && m.citations
            ? Array.from(new Set(m.citations.map((c) => c.filename)))
            : []
        const conflicts =
          m.role === 'assistant' && m.verification?.verdict === 'conflict'
            ? m.verification.conflicts
            : []
        return (
          <div key={i} className={`bubble ${m.role}`}>
            <div className="bubble-text">{renderWithCitations(m.content)}</div>
            {sources.length > 0 && (
              <div className="sources-line">
                <span className="sources-label">Sources</span>
                {sources.map((f, j) => (
                  <span key={j} className="source-chip">
                    {f}
                  </span>
                ))}
              </div>
            )}
            {conflicts.length > 0 && (
              <div className="conflict-flag">
                <span className="conflict-tag">Conflicting sources</span>
                <ul className="conflict-list">
                  {conflicts.map((c, j) => (
                    <li key={j}>{c}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )
      })}
      {partial && (
        <div className="bubble user partial listening">
          <span className="thinking-label">Listening</span>
          <span className="thinking-dots">
            <span />
            <span />
            <span />
          </span>
        </div>
      )}
      {awaitingAnswer && (
        <div className="bubble assistant thinking">
          <span className="thinking-label">{STAGE_LABEL[stage] || 'Working'}</span>
          <span className="thinking-dots">
            <span />
            <span />
            <span />
          </span>
        </div>
      )}
      <div ref={endRef} />
    </div>
  )
}
