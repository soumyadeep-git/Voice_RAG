interface Props {
  listening: boolean
  speaking: boolean
  stage: string
  supported: boolean
  onToggleMic: () => void
}

const STAGE_LABEL: Record<string, string> = {
  idle: 'Ready',
  thinking: 'Searching & verifying…',
  answering: 'Answering…',
}

export function VoiceConsole({ listening, speaking, stage, supported, onToggleMic }: Props) {
  return (
    <div className="voice-console">
      <button
        className={`mic-btn ${listening ? 'on' : ''} ${speaking ? 'speaking' : ''}`}
        onClick={onToggleMic}
        disabled={!supported}
        title={supported ? 'Toggle microphone' : 'Speech not supported in this browser'}
      >
        {listening ? '◉' : '🎙'}
      </button>
      <div className="voice-status">
        <span className="status-line">
          {!supported
            ? 'Use Chrome/Edge for voice'
            : listening
              ? speaking
                ? 'Speaking — talk to interrupt'
                : 'Listening…'
              : 'Mic off'}
        </span>
        <span className="stage muted">{STAGE_LABEL[stage] || stage}</span>
      </div>
    </div>
  )
}
