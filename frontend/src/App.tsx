import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import './App.css'
import { ConversationView } from './components/ConversationView'
import { SourcePanel } from './components/SourcePanel'
import { UploadPanel } from './components/UploadPanel'
import { VoiceConsole } from './components/VoiceConsole'
import { SpeechController, speechSupported } from './lib/speech'
import { VoiceClient } from './lib/voiceClient'
import type { Message, Passage, ServerEvent } from './types'

async function transcribeAudio(audio: Blob): Promise<string> {
  const form = new FormData()
  form.append('audio', audio, 'utterance.webm')
  const res = await fetch('/transcribe', { method: 'POST', body: form })
  if (!res.ok) throw new Error(`transcribe failed: ${res.status}`)
  const data = (await res.json()) as { text?: string }
  return data.text ?? ''
}

async function synthesizeSpeech(text: string, signal: AbortSignal): Promise<Blob> {
  const res = await fetch('/tts', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
    signal,
  })
  if (!res.ok) throw new Error(`tts failed: ${res.status}`)
  return res.blob()
}

export default function App() {
  const [messages, setMessages] = useState<Message[]>([])
  const [partial, setPartial] = useState('')
  const [stage, setStage] = useState('idle')
  const [listening, setListening] = useState(false)
  const [speaking, setSpeaking] = useState(false)
  const [passages, setPassages] = useState<Passage[]>([])
  const [error, setError] = useState<string | null>(null)
  const [connected, setConnected] = useState(false)

  const speechRef = useRef<SpeechController | null>(null)
  const clientRef = useRef<VoiceClient | null>(null)
  const convRef = useRef<string | null>(null)
  const answerRef = useRef('')
  const voiceActiveRef = useRef(false)
  const speakingRef = useRef(false)
  const supported = speechSupported()

  const handleEvent = useCallback((ev: ServerEvent) => {
    switch (ev.type) {
      case 'conversation':
        convRef.current = ev.conversation_id
        break
      case 'status':
        setStage(ev.stage)
        break
      case 'answer_chunk':
        answerRef.current = `${answerRef.current} ${ev.text}`.trim()
        updateAssistant(answerRef.current, undefined, undefined)
        break
      case 'answer_complete':
        updateAssistant(ev.answer, ev.citations, ev.verification)
        setPassages(ev.passages)
        setStage('idle')
        answerRef.current = ''
        // Speak the full answer once it's complete (natural prosody, one
        // synthesis call) rather than choppily per streamed chunk.
        speechRef.current?.speak(ev.answer)
        break
      case 'interrupted':
        setStage('idle')
        break
      case 'notice':
        setError(ev.message)
        setStage('idle')
        break
      case 'error':
        setError(ev.message)
        setStage('idle')
        break
    }
  }, [])

  const updateAssistant = (
    content: string,
    citations?: Passage[],
    verification?: Message['verification'],
  ) => {
    setMessages((prev) => {
      const next = [...prev]
      const last = next[next.length - 1]
      if (last && last.role === 'assistant' && last.pending) {
        next[next.length - 1] = {
          ...last,
          content,
          citations: citations ?? last.citations,
          verification: verification ?? last.verification,
          pending: verification ? false : true,
        }
      } else {
        next.push({ role: 'assistant', content, citations, verification, pending: !verification })
      }
      return next
    })
  }

  const submitQuestion = useCallback((text: string) => {
    if (text.replace(/[^a-zA-Z0-9]/g, '').length < 2) return
    setError(null)
    setPartial('')
    answerRef.current = ''
    setMessages((prev) => [...prev, { role: 'user', content: text }])
    clientRef.current?.ask(text, convRef.current)
  }, [])

  useEffect(() => {
    const client = new VoiceClient(
      handleEvent,
      () => setConnected(true),
      () => setConnected(false),
    )
    client.connect()
    clientRef.current = client

    const speech = new SpeechController(
      {
        onPartial: (t) => setPartial(t),
        onFinal: (t) => {
          setPartial('')
          submitQuestion(t)
        },
        onSpeechStart: () => {
          if (speechRef.current?.isSpeaking()) {
            speechRef.current.cancelSpeech()
            clientRef.current?.interrupt()
            setStage('idle')
          }
        },
        onListeningChange: setListening,
        onSpeakingChange: (s) => {
          setSpeaking(s)
          const was = speakingRef.current
          speakingRef.current = s
          // When the assistant finishes speaking, resume listening for the
          // next turn (hands-free), unless the user turned voice off.
          if (was && !s && voiceActiveRef.current) {
            speechRef.current?.startListening()
          }
        },
        onError: (e) => setError(`Mic: ${e}`),
      },
      transcribeAudio,
      synthesizeSpeech,
    )
    speechRef.current = speech

    return () => {
      client.close()
      speech.stopListening()
      speech.cancelSpeech()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const toggleMic = () => {
    const speech = speechRef.current
    if (!speech) return
    if (listening) {
      voiceActiveRef.current = false
      speech.stopListening()
    } else {
      voiceActiveRef.current = true
      // Tapping the mic while the assistant is talking interrupts it.
      if (speech.isSpeaking()) {
        speech.cancelSpeech()
        clientRef.current?.interrupt()
        setStage('idle')
      }
      speech.startListening()
    }
  }

  return (
    <div className="app">
      <header className="app-header">
        <Link to="/" className="app-brand">
          <span className="mark" />
          ASK_MY_NOTES
        </Link>
        <span className={`conn ${connected ? 'ok' : 'off'}`}>
          {connected ? 'connected' : 'connecting…'}
        </span>
      </header>
      <div className="layout">
        <aside className="left">
          <UploadPanel />
        </aside>
        <main className="center">
          <ConversationView messages={messages} partial={partial} />
          {error && <p className="error banner">{error}</p>}
          <VoiceConsole
            listening={listening}
            speaking={speaking}
            stage={stage}
            supported={supported}
            onToggleMic={toggleMic}
          />
        </main>
        <aside className="right">
          <SourcePanel passages={passages} />
        </aside>
      </div>
    </div>
  )
}
