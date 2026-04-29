import { useState, useRef, useCallback, useEffect } from 'react'
import { useApp } from '../store/AppContext.jsx'
import { useAuth } from '../store/AuthContext.jsx'
import { playCelebration } from '../utils/sounds.js'
import api from '../services/api.js'

const WS_BASE = import.meta.env.VITE_WS_URL || 'ws://localhost:8000'

export function useGeminiLive() {
  const { user } = useAuth()
  const { sessionId, setSessionId, updateTasks, markTaskComplete, setPendingCalendarEvent, setPendingSearch } = useApp()

  const [messages, setMessages] = useState([])
  const [connected, setConnected] = useState(false)
  const [pocaTyping, setPocaTyping] = useState(false)
  const [pocaSpeaking, setPocaSpeaking] = useState(false)

  const wsRef = useRef(null)
  const sessionIdRef = useRef(null)
  const audioCtxRef = useRef(null)
  const sourceRef = useRef(null)
  const audioQueueRef = useRef([])  // chunks waiting to play
  const playingRef = useRef(false)  // true while a chunk is actively playing

  // Stored as a ref so onended always calls the latest version (no stale closures)
  const playNextRef = useRef(null)
  playNextRef.current = async () => {
    if (audioQueueRef.current.length === 0) {
      playingRef.current = false
      setPocaSpeaking(false)
      return
    }

    const base64Data = audioQueueRef.current.shift()
    const ctx = audioCtxRef.current
    if (!ctx) { playingRef.current = false; return }

    try {
      if (ctx.state === 'suspended') await ctx.resume()

      const binaryStr = atob(base64Data)
      const bytes = new Uint8Array(binaryStr.length)
      for (let i = 0; i < binaryStr.length; i++) bytes[i] = binaryStr.charCodeAt(i)

      const audioBuffer = await ctx.decodeAudioData(bytes.buffer)
      const source = ctx.createBufferSource()
      source.buffer = audioBuffer
      source.connect(ctx.destination)
      source.onended = () => {
        if (sourceRef.current === source) sourceRef.current = null
        playNextRef.current()
      }
      sourceRef.current = source
      setPocaSpeaking(true)
      source.start()
    } catch (err) {
      console.error('[POCA audio chunk]', err)
      playNextRef.current()
    }
  }

  const cancelSpeech = useCallback(() => {
    audioQueueRef.current = []
    playingRef.current = false
    if (sourceRef.current) {
      try { sourceRef.current.stop() } catch {}
      sourceRef.current = null
    }
    setPocaSpeaking(false)
  }, [])

  // Called synchronously from the click handler to unlock browser audio
  const initAudio = useCallback(() => {
    if (!audioCtxRef.current) {
      audioCtxRef.current = new AudioContext()
    }
    const ctx = audioCtxRef.current
    if (ctx.state === 'suspended') ctx.resume()
    // Play a silent frame to warm up the audio pipeline
    const buf = ctx.createBuffer(1, 1, 22050)
    const src = ctx.createBufferSource()
    src.buffer = buf
    src.connect(ctx.destination)
    src.start()
  }, [])

  // Enqueue a chunk — starts playing immediately if nothing is in progress
  const playAudio = useCallback((base64Data) => {
    audioQueueRef.current.push(base64Data)
    if (!playingRef.current) {
      playingRef.current = true
      playNextRef.current()
    }
  }, [])

  const addMessage = useCallback((role, content) => {
    setMessages(prev => [...prev, {
      id: crypto.randomUUID(),
      role,
      content,
      timestamp: new Date(),
    }])
  }, [])

  const connect = useCallback(async () => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    let sid = sessionIdRef.current
    if (!sid) {
      const res = await api.post('/sessions/start')
      sid = res.data.id
      sessionIdRef.current = sid
      setSessionId(sid)
    }

    const token = localStorage.getItem('poca_token')
    const localDt = encodeURIComponent(new Date().toLocaleString('en-US', {
      weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
      hour: 'numeric', minute: '2-digit', timeZoneName: 'short',
    }))
    const ws = new WebSocket(`${WS_BASE}/ws/chat/${sid}?token=${token}&local_datetime=${localDt}`)
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
      setPocaTyping(true)
    }

    ws.onmessage = (event) => {
      let msg
      try { msg = JSON.parse(event.data) } catch { return }

      switch (msg.type) {
        case 'session_started':
          break
        case 'text':
          setPocaTyping(false)
          // Show both assistant responses and user speech transcripts
          if (msg.role === 'assistant' || msg.role === 'user') addMessage(msg.role, msg.data)
          break
        case 'audio_response':
          playAudio(msg.data)
          break
        case 'processing':
          setPocaTyping(true)
          break
        case 'dashboard_update':
          if (msg.tasks?.length) updateTasks(msg.tasks)
          break
        case 'task_completed':
          if (user?.celebration_sounds !== false) playCelebration()
          break
        case 'calendar_confirm':
          setPendingCalendarEvent(msg.event)
          break
        case 'search_confirm':
          setPendingSearch(msg.query)
          break
        case 'error':
          addMessage('system', `Error: ${msg.message}`)
          break
      }
    }

    ws.onclose = () => {
      setConnected(false)
      setPocaTyping(false)
    }

    ws.onerror = () => {
      setConnected(false)
    }
  }, [addMessage, setSessionId, updateTasks, setPendingCalendarEvent, setPendingSearch, playAudio, user])

  const disconnect = useCallback(async () => {
    cancelSpeech()
    if (wsRef.current) {
      wsRef.current.send(JSON.stringify({ type: 'end_turn' }))
      wsRef.current.close()
      wsRef.current = null
    }
    if (sessionIdRef.current) {
      try {
        await api.patch(`/sessions/${sessionIdRef.current}/end`, {
          input_tokens: 0,
          output_tokens: 0,
        })
      } catch { /* non-fatal */ }
      sessionIdRef.current = null
      setSessionId(null)
    }
    setConnected(false)
  }, [cancelSpeech, setSessionId])

  const sendText = useCallback((text) => {
    if (!text.trim() || wsRef.current?.readyState !== WebSocket.OPEN) return
    cancelSpeech()
    addMessage('user', text)
    setPocaTyping(true)
    wsRef.current.send(JSON.stringify({ type: 'text', data: text }))
  }, [addMessage, cancelSpeech])

  // Send a PCM16 audio chunk (base64) from the microphone to the backend
  const sendAudioChunk = useCallback((base64pcm) => {
    if (wsRef.current?.readyState !== WebSocket.OPEN) return
    wsRef.current.send(JSON.stringify({ type: 'audio_chunk', data: base64pcm }))
  }, [])

  // Signal end of user speech turn so Gemini knows to respond
  const sendAudioEnd = useCallback(() => {
    if (wsRef.current?.readyState !== WebSocket.OPEN) return
    cancelSpeech()
    setPocaTyping(true)
    wsRef.current.send(JSON.stringify({ type: 'audio_end' }))
  }, [cancelSpeech])

  useEffect(() => {
    return () => {
      if (wsRef.current) wsRef.current.close()
      if (audioCtxRef.current) audioCtxRef.current.close()
    }
  }, [])

  return { messages, connected, pocaTyping, pocaSpeaking, connect, disconnect, sendText, sendAudioChunk, sendAudioEnd, cancelSpeech, initAudio }
}
