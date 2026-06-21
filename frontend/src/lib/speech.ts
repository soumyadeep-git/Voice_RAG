/* eslint-disable @typescript-eslint/no-explicit-any */

export interface SpeechHandlers {
  onPartial?: (text: string) => void
  onFinal?: (text: string) => void
  onSpeechStart?: () => void
  onListeningChange?: (listening: boolean) => void
  onSpeakingChange?: (speaking: boolean) => void
  onError?: (message: string) => void
}

const SpeechRecognitionImpl: any =
  (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition

export function speechSupported(): boolean {
  return Boolean(SpeechRecognitionImpl) && 'speechSynthesis' in window
}

function stripCitations(text: string): string {
  return text.replace(/\[\d+\]/g, '').replace(/\s{2,}/g, ' ').trim()
}

export class SpeechController {
  private recognition: any
  private handlers: SpeechHandlers
  private wantListening = false
  private speaking = false
  private queue: string[] = []

  constructor(handlers: SpeechHandlers) {
    this.handlers = handlers
    if (!SpeechRecognitionImpl) return
    const rec = new SpeechRecognitionImpl()
    rec.continuous = true
    rec.interimResults = true
    rec.lang = 'en-US'

    rec.onresult = (event: any) => {
      let interim = ''
      let final = ''
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i]
        if (result.isFinal) final += result[0].transcript
        else interim += result[0].transcript
      }
      if (this.speaking && (interim.trim().length > 1 || final.trim().length > 1)) {
        this.handlers.onSpeechStart?.()
      }
      if (interim) this.handlers.onPartial?.(interim)
      if (final.trim()) this.handlers.onFinal?.(final.trim())
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

  startListening() {
    if (!this.recognition) return
    this.wantListening = true
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
    this.recognition.stop()
  }

  speak(text: string) {
    const clean = stripCitations(text)
    if (!clean) return
    this.queue.push(clean)
    if (!this.speaking) this.playNext()
  }

  private playNext() {
    const next = this.queue.shift()
    if (!next) {
      this.speaking = false
      this.handlers.onSpeakingChange?.(false)
      return
    }
    this.speaking = true
    this.handlers.onSpeakingChange?.(true)
    const utterance = new SpeechSynthesisUtterance(next)
    utterance.rate = 1.05
    utterance.onend = () => this.playNext()
    utterance.onerror = () => this.playNext()
    window.speechSynthesis.speak(utterance)
  }

  cancelSpeech() {
    this.queue = []
    window.speechSynthesis.cancel()
    this.speaking = false
    this.handlers.onSpeakingChange?.(false)
  }

  isSpeaking() {
    return this.speaking
  }
}
