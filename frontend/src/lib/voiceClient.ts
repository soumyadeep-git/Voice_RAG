import type { ServerEvent } from '../types'

export class VoiceClient {
  private ws: WebSocket | null = null
  private onEvent: (e: ServerEvent) => void
  private onOpen?: () => void
  private onClose?: () => void

  constructor(onEvent: (e: ServerEvent) => void, onOpen?: () => void, onClose?: () => void) {
    this.onEvent = onEvent
    this.onOpen = onOpen
    this.onClose = onClose
  }

  connect() {
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    this.ws = new WebSocket(`${proto}://${window.location.host}/ws`)
    this.ws.onopen = () => this.onOpen?.()
    this.ws.onclose = () => this.onClose?.()
    this.ws.onmessage = (ev) => {
      try {
        this.onEvent(JSON.parse(ev.data))
      } catch {
        /* ignore malformed */
      }
    }
  }

  ask(question: string, conversationId: string | null) {
    this.send({ type: 'ask', question, conversation_id: conversationId })
  }

  interrupt() {
    this.send({ type: 'interrupt' })
  }

  private send(payload: unknown) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(payload))
    }
  }

  get ready() {
    return this.ws?.readyState === WebSocket.OPEN
  }

  close() {
    this.ws?.close()
  }
}
