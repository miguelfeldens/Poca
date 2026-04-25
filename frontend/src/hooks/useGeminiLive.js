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

  const wsRef = useRef(null)
  const sessionIdRef = useRef(null)

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

    // Start a new session
    let sid = sessionIdRef.current
    if (!sid) {
      const res = await api.post('/sessions/start')
      sid = res.data.id
      sessionIdRef.current = sid
      setSessionId(sid)
    }

    const token = localStorage.getItem('poca_token')
    const ws = new WebSocket(`${WS_BASE}/ws/chat/${sid}?token=${token}`)
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
    }

    ws.onmessage = (event) => {
      let msg
      try {
        msg = JSON.parse(event.data)
      } catch {
        return
      }

      switch (msg.type) {
        case 'session_started':
          break
        case 'text':
          setPocaTyping(false)
          if (msg.role === 'assistant') {
            addMessage('assistant', msg.data)
          }
          break
        case 'processing':
          setPocaTyping(true)
          break
        case 'dashboard_update':
          if (msg.tasks?.length) {
            updateTasks(msg.tasks)
          }
          break
        case 'task_completed':
          if (user?.celebration_sounds !== false) {
            playCelebration()
          }
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
  }, [addMessage, setSessionId, updateTasks, markTaskComplete, setPendingCalendarEvent, setPendingSearch, user])

  const disconnect = useCallback(async () => {
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
      } catch {
        // Non-fatal
      }
      sessionIdRef.current = null
      setSessionId(null)
    }
    setConnected(false)
  }, [setSessionId])

  const sendText = useCallback((text) => {
    if (!text.trim() || wsRef.current?.readyState !== WebSocket.OPEN) return
    addMessage('user', text)
    setPocaTyping(true)
    wsRef.current.send(JSON.stringify({ type: 'text', data: text }))
  }, [addMessage])

  const sendAudio = useCallback((base64Audio) => {
    if (wsRef.current?.readyState !== WebSocket.OPEN) return
    setPocaTyping(true)
    wsRef.current.send(JSON.stringify({ type: 'audio', data: base64Audio }))
  }, [])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (wsRef.current) wsRef.current.close()
    }
  }, [])

  return { messages, connected, pocaTyping, connect, disconnect, sendText, sendAudio }
}
