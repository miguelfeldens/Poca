import { Mic, MicOff } from 'lucide-react'
import { useVoiceInput } from '../../hooks/useVoiceInput.js'

export default function VoiceButton({ onTranscript, onAudioChunk }) {
  const { listening, supported, toggleListening } = useVoiceInput({
    onTranscript,
    onAudioChunk,
  })

  if (!supported) return null

  return (
    <button
      className={`voice-btn ${listening ? 'listening' : ''}`}
      onClick={toggleListening}
      aria-label={listening ? 'Stop listening' : 'Start voice input'}
      title={listening ? 'Tap to stop' : 'Tap to speak'}
    >
      {listening ? <MicOff size={20} /> : <Mic size={20} />}
      {listening && <span className="pulse-ring" />}
    </button>
  )
}
