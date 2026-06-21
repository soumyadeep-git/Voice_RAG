import { useEffect, useRef, useState } from 'react'
import { deleteDocument, listDocuments, uploadDocuments } from '../lib/api'
import type { DocumentItem } from '../types'

export function UploadPanel() {
  const [docs, setDocs] = useState<DocumentItem[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const refresh = async () => {
    try {
      setDocs(await listDocuments())
    } catch {
      setError('Could not load documents')
    }
  }

  useEffect(() => {
    refresh()
    const processing = docs.some((d) => d.status === 'processing' || d.status === 'pending')
    const interval = setInterval(refresh, processing ? 1500 : 5000)
    return () => clearInterval(interval)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [docs.map((d) => d.status).join(',')])

  const onFiles = async (files: FileList | null) => {
    if (!files || files.length === 0) return
    setBusy(true)
    setError(null)
    try {
      const res = await uploadDocuments(files)
      if (res.rejected.length) {
        setError(res.rejected.map((r) => `${r.filename}: ${r.reason}`).join('; '))
      }
      await refresh()
    } catch {
      setError('Upload failed')
    } finally {
      setBusy(false)
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  return (
    <div className="panel">
      <h2>Documents</h2>
      <div
        className="dropzone"
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault()
          onFiles(e.dataTransfer.files)
        }}
      >
        {busy ? 'Uploading…' : 'Drop PDF / TXT / MD files here, or click to browse'}
        <input
          ref={inputRef}
          type="file"
          multiple
          accept=".pdf,.txt,.md,.markdown"
          hidden
          onChange={(e) => onFiles(e.target.files)}
        />
      </div>
      {error && <p className="error">{error}</p>}
      <ul className="doc-list">
        {docs.length === 0 && <li className="muted">No documents yet.</li>}
        {docs.map((d) => (
          <li key={d.id} className="doc-item">
            <div>
              <span className="doc-name">{d.filename}</span>
              <span className={`badge badge-${d.status}`}>{d.status}</span>
              {d.status === 'ready' && <span className="muted"> · {d.num_chunks} chunks</span>}
            </div>
            <button
              className="link-danger"
              onClick={async () => {
                await deleteDocument(d.id)
                refresh()
              }}
            >
              remove
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
