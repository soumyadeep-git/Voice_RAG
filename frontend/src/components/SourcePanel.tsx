import type { Passage } from '../types'

function location(p: Passage): string {
  const parts: string[] = []
  if (p.page != null) parts.push(`p.${p.page}`)
  if (p.section) parts.push(p.section)
  return parts.join(' · ')
}

export function SourcePanel({ passages }: { passages: Passage[] }) {
  return (
    <div className="panel sources">
      <h2>Cited sources</h2>
      {passages.length === 0 && <p className="muted">Sources for the latest answer appear here.</p>}
      <ul className="source-list">
        {passages.map((p) => (
          <li key={p.id} className="source-item">
            <div className="source-head">
              <span className="cite-num">[{p.n}]</span>
              <span className="source-file">{p.filename}</span>
              {location(p) && <span className="muted"> · {location(p)}</span>}
            </div>
            <p className="source-text">{p.text}</p>
          </li>
        ))}
      </ul>
    </div>
  )
}
