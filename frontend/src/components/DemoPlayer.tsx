import { useEffect, useRef, useState, type ChangeEvent } from 'react'

const QUESTION = 'What does GDPR say about consent?'
const ANSWER =
  'Under GDPR, consent must be freely given, specific, informed, and unambiguous. Pre-ticked boxes do not count as valid consent.'
const ANSWER_WORDS = ANSWER.split(' ')

// Timeline markers in milliseconds.
const T_LISTEN = 500
const T_TYPE_END = 2600
const T_SEARCH = 3300
const T_VERIFY = 3900
const T_ANSWER_START = 4100
const T_ANSWER_END = 7100
const T_CITE = 5600
const T_STAMP = 7100
const T_TOTAL = 9600

type Phase = 'ready' | 'listening' | 'searching' | 'verifying' | 'answering' | 'grounded'

function phaseFor(t: number): Phase {
  if (t < T_LISTEN) return 'ready'
  if (t < T_TYPE_END) return 'listening'
  if (t < T_SEARCH) return 'searching'
  if (t < T_VERIFY) return 'verifying'
  if (t < T_ANSWER_END) return 'answering'
  return 'grounded'
}

const STATUS_LABEL: Record<Phase, string> = {
  ready: 'READY',
  listening: 'LISTENING',
  searching: 'SEARCHING DOCUMENTS',
  verifying: 'VERIFYING GROUNDING',
  answering: 'ANSWERING',
  grounded: 'GROUNDED',
}

function clampFraction(t: number, start: number, end: number): number {
  if (t <= start) return 0
  if (t >= end) return 1
  return (t - start) / (end - start)
}

export function DemoPlayer() {
  const [t, setT] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [started, setStarted] = useState(false)
  const rafRef = useRef<number | null>(null)
  const lastTsRef = useRef<number | null>(null)
  const tRef = useRef(0)

  useEffect(() => {
    if (!playing) {
      lastTsRef.current = null
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
      return
    }
    const loop = (ts: number) => {
      if (lastTsRef.current == null) lastTsRef.current = ts
      const dt = ts - lastTsRef.current
      lastTsRef.current = ts
      tRef.current = (tRef.current + dt) % T_TOTAL
      setT(tRef.current)
      rafRef.current = requestAnimationFrame(loop)
    }
    rafRef.current = requestAnimationFrame(loop)
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
    }
  }, [playing])

  const toggle = () => {
    setStarted(true)
    setPlaying((p) => !p)
  }

  const scrub = (e: ChangeEvent<HTMLInputElement>) => {
    const next = (Number(e.target.value) / 1000) * T_TOTAL
    tRef.current = next
    setT(next)
  }

  const phase = phaseFor(t)
  const typed = QUESTION.slice(0, Math.round(clampFraction(t, T_LISTEN, T_TYPE_END) * QUESTION.length))
  const wordCount = Math.round(clampFraction(t, T_ANSWER_START, T_ANSWER_END) * ANSWER_WORDS.length)
  const answerText = ANSWER_WORDS.slice(0, wordCount).join(' ')
  const showCite = t >= T_CITE
  const showStamp = t >= T_STAMP
  const micActive = phase === 'listening'
  const thinking = phase === 'searching' || phase === 'verifying'

  return (
    <div className="demo">
      <div className="demo-frame">
        <div className="demo-bar">
          <span className="demo-dot" />
          <span className="demo-dot demo-dot--amber" />
          <span className="demo-dot demo-dot--green" />
          <span className="demo-bar-title">ask_my_notes — live session</span>
          <span className={`demo-stage demo-stage--${phase}`}>{STATUS_LABEL[phase]}</span>
        </div>

        <div className="demo-screen">
          <div className="demo-row demo-row--user">
            <div className="demo-bubble demo-bubble--user">
              {typed || '\u00A0'}
              {micActive && <span className="demo-caret" />}
            </div>
            <div className={`demo-mic ${micActive ? 'is-on' : ''}`}>
              <span className="demo-wave" />
              <span className="demo-wave" />
              <span className="demo-wave" />
            </div>
          </div>

          {thinking && (
            <div className="demo-thinking">
              <span className="demo-spinner" />
              <span>{phase === 'searching' ? 'retrieving passages…' : 'checking every claim…'}</span>
            </div>
          )}

          {answerText && (
            <div className="demo-row demo-row--bot">
              <div className="demo-bubble demo-bubble--bot">
                <p className="demo-answer">{answerText}</p>
                {showCite && (
                  <span className="demo-cite">[1] gdpr_consent_and_childrens_data.md</span>
                )}
                {showStamp && <span className="demo-stamp">GROUNDED</span>}
              </div>
            </div>
          )}
        </div>

        {!started && (
          <button className="demo-poster" onClick={toggle} aria-label="Play demo">
            <span className="demo-poster-play">▶</span>
            <span className="demo-poster-text">Play a 10-second walkthrough</span>
          </button>
        )}
      </div>

      <div className="demo-controls">
        <button className="demo-play" onClick={toggle} aria-label={playing ? 'Pause' : 'Play'}>
          {playing ? '❚❚' : '▶'}
        </button>
        <input
          className="demo-progress"
          type="range"
          min={0}
          max={1000}
          value={Math.round((t / T_TOTAL) * 1000)}
          onChange={scrub}
          aria-label="Demo progress"
        />
        <span className="demo-time">
          {(t / 1000).toFixed(1)}s / {(T_TOTAL / 1000).toFixed(0)}s
        </span>
      </div>
    </div>
  )
}
