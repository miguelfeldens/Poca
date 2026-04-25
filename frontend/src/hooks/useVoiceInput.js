import { useState, useRef, useCallback } from 'react'

export function useVoiceInput({ onTranscript, onAudioChunk }) {
  const [listening, setListening] = useState(false)
  const [supported, setSupported] = useState(
    typeof window !== 'undefined' && 'webkitSpeechRecognition' in window || 'SpeechRecognition' in window
  )

  const recognitionRef = useRef(null)
  const mediaRecorderRef = useRef(null)

  const startListening = useCallback(() => {
    if (listening) return

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SpeechRecognition) {
      setSupported(false)
      return
    }

    const recognition = new SpeechRecognition()
    recognition.continuous = false
    recognition.interimResults = false
    recognition.lang = 'en-US'

    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript
      if (transcript && onTranscript) {
        onTranscript(transcript)
      }
    }

    recognition.onend = () => {
      setListening(false)
    }

    recognition.onerror = () => {
      setListening(false)
    }

    recognition.start()
    recognitionRef.current = recognition
    setListening(true)
  }, [listening, onTranscript])

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
