export interface DocumentItem {
  id: string
  filename: string
  num_chunks: number
  status: string
  error?: string | null
}

export interface Passage {
  n: number
  id: string
  text: string
  filename: string
  page?: number | null
  section?: string | null
}

export interface ClaimCheck {
  claim: string
  status: string
  citations: number[]
  note?: string
}

export interface Verification {
  verified_answer: string
  verdict: string
  grounded: boolean
  claims: ClaimCheck[]
  conflicts: string[]
}

export interface Message {
  role: 'user' | 'assistant'
  content: string
  citations?: Passage[]
  verification?: Verification
  pending?: boolean
}

export type ServerEvent =
  | { type: 'conversation'; conversation_id: string }
  | { type: 'status'; stage: string }
  | { type: 'rewritten'; query: string }
  | { type: 'answer_chunk'; text: string }
  | {
      type: 'answer_complete'
      answer: string
      verification: Verification
      citations: Passage[]
      passages: Passage[]
      interrupted: boolean
    }
  | { type: 'interrupted' }
  | { type: 'error'; message: string }
