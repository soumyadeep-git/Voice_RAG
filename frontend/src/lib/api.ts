import type { DocumentItem } from '../types'

export async function listDocuments(): Promise<DocumentItem[]> {
  const res = await fetch('/documents')
  if (!res.ok) throw new Error('Failed to load documents')
  return res.json()
}

export async function uploadDocuments(files: FileList | File[]): Promise<{
  accepted: DocumentItem[]
  rejected: { filename: string; reason: string }[]
}> {
  const form = new FormData()
  Array.from(files).forEach((f) => form.append('files', f))
  const res = await fetch('/documents', { method: 'POST', body: form })
  if (!res.ok) throw new Error('Upload failed')
  return res.json()
}

export async function deleteDocument(id: string): Promise<void> {
  const res = await fetch(`/documents/${id}`, { method: 'DELETE' })
  if (!res.ok) throw new Error('Delete failed')
}
