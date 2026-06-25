/* eslint-disable @typescript-eslint/no-explicit-any */

export interface SpeechHandlers {
  onPartial?: (text: string) => void
  onFinal?: (text: string) => void
  onSpeechStart?: () => void
  onListeningChange?: (listening: boolean) => void
  onSpeakingChange?: (speaking: boolean) => void
  onError?: (message: string) => void
}

// Optional accurate transcriber (e.g. Groq Whisper). Receives the recorded
// utterance audio and returns the transcript. If omitted or it fails, the
// browser's own transcript is used as a fallback.
export type Transcriber = (audio: Blob) => Promise<string>

// Optional natural-voice synthesizer (e.g. Cartesia). Returns spoken audio for
// the text. If omitted or it fails, the browser speechSynthesis is used.
export type Synthesizer = (text: string, signal: AbortSignal) => Promise<Blob>

const SpeechRecognitionImpl: any =
  (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition

// How long the speaker can pause before we treat the utterance as complete
// and send it for answering (lightweight voice-activity endpointing).
const ENDPOINT_SILENCE_MS = 1200

// Recordings shorter than this are almost certainly blips/echo, not a real
// question. We discard them rather than risk a hallucinated transcript.
const MIN_UTTERANCE_MS = 400

// Preferred natural-sounding female English voices, in priority order.
// Names vary by OS/browser; the first available match wins.
const VOICE_PREFERENCES = [
  /Aria/i,
  /Jenny/i,
  /Google US English$/i,
  /Google UK English Female/i,
  /Samantha/i,
  /Serena/i,
  /Karen/i,
  /Tessa/i,
  /Victoria/i,
  /Allison/i,
  /Moira/i,
  /Fiona/i,
]

export function speechSupported(): boolean {
  return Boolean(SpeechRecognitionImpl) && 'speechSynthesis' in window
}

function stripCitations(text: string): string {
  return text.replace(/\[\d+\]/g, '').replace(/\s{2,}/g, ' ').trim()
}

export class SpeechController {
  private recognition: any
  private handlers: SpeechHandlers
  private transcriber?: Transcriber
  private synthesizer?: Synthesizer
  private wantListening = false
  private speaking = false
  private queue: string[] = []
  private finalText = ''
  private latestCombined = ''
  private endpointTimer: ReturnType<typeof setTimeout> | null = null
  private voice: SpeechSynthesisVoice | null = null
  private mediaStream: MediaStream | null = null
  private recorder: MediaRecorder | null = null
  private chunks: Blob[] = []
  private recording = false
  private recordingStartedAt = 0
  private currentAudio: HTMLAudioElement | null = null
  private ttsAbort: AbortController | null = null
  private cancelled = false

  constructor(handlers: SpeechHandlers, transcriber?: Transcriber, synthesizer?: Synthesizer) {
    this.handlers = handlers
    this.transcriber = transcriber
    this.synthesizer = synthesizer
    this.loadVoice()
    if ('speechSynthesis' in window) {
      window.speechSynthesis.onvoiceschanged = () => this.loadVoice()
    }

    if (!SpeechRecognitionImpl) return
    const rec = new SpeechRecognitionImpl()
    rec.continuous = true
    rec.interimResults = true
    rec.lang = 'en-US'
    rec.maxAlternatives = 1

    rec.onresult = (event: any) => {
      let interim = ''
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i]
        if (result.isFinal) this.finalText += result[0].transcript + ' '
        else interim += result[0].transcript
      }
      const combined = (this.finalText + interim).trim()
      this.latestCombined = combined

      // Barge-in: real speech while the assistant is talking interrupts it.
      if (this.speaking && combined.length > 1) {
        this.handlers.onSpeechStart?.()
      }
      if (combined) {
        this.handlers.onPartial?.(combined)
      }

      // Reset the silence timer on every new bit of speech. When the speaker
      // pauses long enough, commit the whole utterance as one question.
      this.scheduleEndpoint()
    }

    rec.onerror = (event: any) => {
      if (event.error !== 'no-speech' && event.error !== 'aborted') {
        this.handlers.onError?.(event.error)
      }
    }

    rec.onend = () => {
      if (this.wantListening) {
        try {
          rec.start()
        } catch {
          /* already started */
        }
      } else {
        this.handlers.onListeningChange?.(false)
      }
    }

    this.recognition = rec
  }

  private scheduleEndpoint() {
    if (this.endpointTimer) clearTimeout(this.endpointTimer)
    this.endpointTimer = setTimeout(() => this.commit(), ENDPOINT_SILENCE_MS)
  }

  private commit() {
    const browserText = this.latestCombined.trim()
    this.finalText = ''
    this.latestCombined = ''
    this.endpointTimer = null

    const meaningful = browserText.replace(/[^a-zA-Z0-9]/g, '').length >= 2
    if (!meaningful) {
      this.discardRecording()
      return
    }

    // The user finished a turn: stop listening so the mic isn't "on" while we
    // transcribe, search and speak. It auto-resumes after the answer is spoken.
    this.endTurn()

    if (this.transcriber && this.recording && this.recorder) {
      // Too-short clips are blips/echo, not real speech: discard rather than
      // submitting a likely-hallucinated transcript.
      if (Date.now() - this.recordingStartedAt < MIN_UTTERANCE_MS) {
        this.discardRecording()
        return
      }
      const recorder = this.recorder
      recorder.onstop = async () => {
        // ondataavailable has fired by now, so this.chunks holds the audio.
        const blob = new Blob(this.chunks, { type: recorder.mimeType || 'audio/webm' })
        this.chunks = []
        this.recorder = null
        this.recording = false
        // Release the mic now that the turn's audio is captured.
        this.releaseStream()
        let text = browserText
        try {
          const transcript = (await this.transcriber!(blob)).trim()
          if (transcript) text = transcript
        } catch {
          /* keep the browser transcript */
        }
        this.handlers.onFinal?.(text)
      }
      try {
        recorder.stop()
      } catch {
        this.recording = false
        this.handlers.onFinal?.(browserText)
      }
    } else {
      this.handlers.onFinal?.(browserText)
    }
  }

  private endTurn() {
    this.wantListening = false
    if (this.endpointTimer) {
      clearTimeout(this.endpointTimer)
      this.endpointTimer = null
    }
    try {
      this.recognition?.stop()
    } catch {
      /* ignore */
    }
  }

  private startRecording() {
    if (!this.transcriber || !this.mediaStream || this.recording) return
    try {
      this.chunks = []
      this.recorder = new MediaRecorder(this.mediaStream, { audioBitsPerSecond: 128000 })
      this.recorder.ondataavailable = (e) => {
        if (e.data.size) this.chunks.push(e.data)
      }
      this.recorder.start()
      this.recording = true
      this.recordingStartedAt = Date.now()
    } catch {
      this.recording = false
    }
  }

  private discardRecording() {
    if (this.recorder && this.recording) {
      this.recorder.onstop = null
      try {
        this.recorder.stop()
      } catch {
        /* ignore */
      }
    }
    this.recorder = null
    this.chunks = []
    this.recording = false
    this.releaseStream()
  }

  private releaseStream() {
    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach((t) => t.stop())
      this.mediaStream = null
    }
  }

  async startListening() {
    if (!this.recognition) return
    this.wantListening = true
    this.finalText = ''
    this.latestCombined = ''
    if (this.transcriber) {
      if (!this.mediaStream) {
        try {
          // Clean capture (echo cancellation / noise suppression / gain) gives
          // Whisper a much better signal and cuts mis-hearings.
          this.mediaStream = await navigator.mediaDevices.getUserMedia({
            audio: {
              echoCancellation: true,
              noiseSuppression: true,
              autoGainControl: true,
              channelCount: 1,
            },
          })
        } catch {
          // No mic access for recording; fall back to browser-only transcript.
          this.mediaStream = null
        }
      }
      // Start recording immediately so the whole utterance is captured from
      // the first word (recognition-detected speech lags and would clip it).
      this.startRecording()
    }
    try {
      this.recognition.start()
      this.handlers.onListeningChange?.(true)
    } catch {
      /* already running */
    }
  }

  stopListening() {
    if (!this.recognition) return
    this.wantListening = false
    if (this.endpointTimer) {
      clearTimeout(this.endpointTimer)
      this.endpointTimer = null
    }
    this.discardRecording()
    this.recognition.stop()
  }

  private loadVoice() {
    if (!('speechSynthesis' in window)) return
    const voices = window.speechSynthesis
      .getVoices()
      .filter((v) => v.lang?.toLowerCase().startsWith('en'))
    if (!voices.length) return
    for (const pref of VOICE_PREFERENCES) {
      const hit = voices.find((v) => pref.test(v.name))
      if (hit) {
        this.voice = hit
        return
      }
    }
    this.voice =
      voices.find((v) => /female/i.test(v.name)) ||
      voices.find((v) => v.lang === 'en-US') ||
      voices[0]
  }

  speak(text: string) {
    const clean = stripCitations(text)
    if (!clean) return
    this.cancelled = false
    this.queue.push(clean)
    if (!this.speaking) {
      this.speaking = true
      this.handlers.onSpeakingChange?.(true)
      void this.playNext()
    }
  }

  private async playNext(): Promise<void> {
    if (this.cancelled) return
    const next = this.queue.shift()
    if (next === undefined) {
      this.speaking = false
      this.handlers.onSpeakingChange?.(false)
      return
    }

    // Prefer the natural Cartesia voice; fall back to the browser voice if the
    // synthesizer is missing or fails.
    if (this.synthesizer) {
      try {
        this.ttsAbort = new AbortController()
        const blob = await this.synthesizer(next, this.ttsAbort.signal)
        if (this.cancelled) return
        await this.playAudioBlob(blob)
        if (this.cancelled) return
        return this.playNext()
      } catch (err) {
        if (this.cancelled || (err as Error)?.name === 'AbortError') return
        // fall through to browser voice
      }
    }
    this.speakBrowser(next, () => {
      if (!this.cancelled) void this.playNext()
    })
  }

  private playAudioBlob(blob: Blob): Promise<void> {
    return new Promise((resolve) => {
      const url = URL.createObjectURL(blob)
      const audio = new Audio(url)
      this.currentAudio = audio
      const done = () => {
        URL.revokeObjectURL(url)
        if (this.currentAudio === audio) this.currentAudio = null
        resolve()
      }
      audio.onended = done
      audio.onerror = done
      audio.play().catch(done)
    })
  }

  private speakBrowser(text: string, onDone: () => void) {
    if (!('speechSynthesis' in window)) {
      onDone()
      return
    }
    const utterance = new SpeechSynthesisUtterance(text)
    if (this.voice) utterance.voice = this.voice
    utterance.rate = 1.0
    utterance.pitch = 1.08
    utterance.onend = onDone
    utterance.onerror = onDone
    window.speechSynthesis.speak(utterance)
  }

  cancelSpeech() {
    this.cancelled = true
    this.queue = []
    if (this.ttsAbort) {
      this.ttsAbort.abort()
      this.ttsAbort = null
    }
    if (this.currentAudio) {
      this.currentAudio.pause()
      this.currentAudio.src = ''
      this.currentAudio = null
    }
    if ('speechSynthesis' in window) window.speechSynthesis.cancel()
    this.speaking = false
    this.handlers.onSpeakingChange?.(false)
  }

  isSpeaking() {
    return this.speaking
  }
}
