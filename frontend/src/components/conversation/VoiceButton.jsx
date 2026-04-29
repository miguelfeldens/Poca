import { forwardRef, useImperativeHandle, useCallback } from 'react'
import { Mic, MicOff } from 'lucide-react'
import { useVoiceInput } from '../../hooks/useVoiceInput.js'

const VoiceButton = forwardRef(function VoiceButton(
  { onChunk, onEnd, onStartListening, disabled, speaking },
  ref
) {
  const { listening, supported, startListening, stopListening } = useVoiceInput({
    onChunk,
    onEnd,
  })

  const handleStart = useCallback(() => {
    onStartListening?.()
    startListening()
  }, [onStartListening, startListening])

  useImperativeHandle(ref, () => ({ startListening: handleStart }), [handleStart])

  if (!supported) return (
    <div className="voice-orb unsupported" title="Voice not supported in this browser">
      <MicOff size={28} />
      <span className="orb-label">Voice unavailable</span>
    </div>
  )

  const label = speaking
    ? 'POCA is speaking…'
    : disabled
    ? 'POCA is thinking…'
    : listening
    ? 'Listening…'
    : 'Tap to speak'

  return (
    <button
      className={`voice-orb ${listening ? 'listening' : ''} ${disabled ? 'disabled' : ''}`}
      onClick={disabled ? undefined : (listening ? stopListening : handleStart)}
      aria-label={listening ? 'Stop listening' : 'Tap to speak'}
      title={listening ? 'Tap to stop' : 'Tap to speak'}
      disabled={disabled}
    >
      <Mic size={28} />
      {listening && (
        <>
          <span className="orb-ring ring-1" />
          <span className="orb-ring ring-2" />
          <span className="orb-ring ring-3" />
        </>
      )}
      <span className="orb-label">{label}</span>
    </button>
  )
})

export default VoiceButton
