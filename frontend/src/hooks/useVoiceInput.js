import { useState, useRef, useCallback, useEffect } from 'react'

export function useVoiceInput({ onTranscript, onAudioChunk, autoStart }) {
  const [listening, setListening] = useState(false)
  const [supported] = useState(
    typeof window !== 'undefined' &&
    ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window)
  )

  const recognitionRef = useRef(null)
  const autoStartRef = useRef(autoStart)

  useEffect(() => {
    autoStartRef.current = autoStart
  }, [autoStart])

  const startListening = useCallback(() => {
    if (listening || !supported) return

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    const recognition = new SpeechRecognition()
    recognition.continuous = false
    recognition.interimResults = false
    recognition.lang = 'en-US'

    recognition.onresult = (event) => {
      const result = event.results[0][0]
      const transcript = result.transcript?.trim()
      const confidence = result.confidence ?? 1
      // Ignore low-confidence results (ambient noise) and very short fragments
      if (transcript && transcript.length > 2 && confidence > 0.55 && onTranscript) {
        onTranscript(transcript)
      }
    }

    recognition.onend = () => {
      setListening(false)
      recognitionRef.current = null
    }

    recognition.onerror = () => {
      setListening(false)
      recognitionRef.current = null
    }

    recognition.start()
    recognitionRef.current = recognition
    setListening(true)
  }, [listening, supported, onTranscript])

  const stopListening = useCallback(() => {
    if (recognitionRef.current) {
      recognitionRef.current.stop()
      recognitionRef.current = null
    }
    setListening(false)
  }, [])

  const toggleListening = useCallback(() => {
    if (listening) stopListening()
    else startListening()
  }, [listening, startListening, stopListening])

  return { listening, supported, toggleListening, startListening, stopListening }
}
