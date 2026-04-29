import { useEffect, useRef, useState, useCallback } from 'react'
import { useGeminiLive } from '../../hooks/useGeminiLive.js'
import MessageList from '../conversation/MessageList.jsx'
import TextInput from '../conversation/TextInput.jsx'
import VoiceButton from '../conversation/VoiceButton.jsx'
import { useAuth } from '../../store/AuthContext.jsx'
import { Power, Keyboard, LogOut } from 'lucide-react'

export default function ConversationPanel() {
  const { user, logout } = useAuth()
  const { messages, connected, pocaTyping, pocaSpeaking, connect, disconnect, sendText, sendAudioChunk, sendAudioEnd, cancelSpeech, initAudio } = useGeminiLive()
  const [showText, setShowText] = useState(false)
  const [sessionStarted, setSessionStarted] = useState(false)
  const voiceRef = useRef(null)

  // Cleanup on unmount only
  useEffect(() => {
    return () => { disconnect() }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Start session: this click IS the user gesture that unlocks browser audio
  const handleStartSession = useCallback(() => {
    initAudio()       // must be called synchronously in the click handler
    setSessionStarted(true)
    connect()
  }, [initAudio, connect])

  const micDisabled = !connected || pocaTyping || pocaSpeaking

  // Status label shown during slow startup (loading calendar/email context)
  const loadingStatus = !sessionStarted
    ? null
    : !connected
    ? 'Connecting to POCA…'
    : messages.length === 0 && pocaTyping
    ? 'Loading your calendar & email context…'
    : null

  return (
    <div className="conversation-panel">
      {/* Header */}
      <div className="conversation-header">
        <div className="user-info">
          {user?.avatar_url && (
            <img src={user.avatar_url} alt={user.name} className="avatar" />
          )}
          <span className="user-name">Hi, {user?.name?.split(' ')[0]}!</span>
        </div>
        <div className="connection-status">
          <span className={`status-dot ${connected ? 'online' : 'offline'}`} />
          <span>{connected ? 'Connected' : sessionStarted ? 'Connecting…' : 'Ready'}</span>
          {sessionStarted && !connected && (
            <button className="icon-btn" onClick={connect} title="Reconnect">
              <Power size={14} />
            </button>
          )}
          <button
            className="icon-btn"
            onClick={logout}
            title="Sign out (re-login to update permissions)"
          >
            <LogOut size={14} />
          </button>
        </div>
      </div>

      {/* Messages */}
      <MessageList messages={messages} typing={pocaTyping} />

      {/* Voice-first input area */}
      <div className="voice-input-area">
        {/* Loading status during startup */}
        {loadingStatus && (
          <p className="loading-status">{loadingStatus}</p>
        )}

        {!sessionStarted ? (
          /* First-time start button — also serves as the browser audio unlock gesture */
          <button className="voice-orb start-orb" onClick={handleStartSession}>
            <span style={{ fontSize: 28 }}>👋</span>
            <span className="orb-label">Tap to start</span>
          </button>
        ) : (
          <VoiceButton
            ref={voiceRef}
            onChunk={sendAudioChunk}
            onEnd={sendAudioEnd}
            onStartListening={cancelSpeech}
            disabled={micDisabled}
            speaking={pocaSpeaking}
          />
        )}

        {/* Keyboard toggle */}
        {sessionStarted && (
          <button
            className={`keyboard-toggle icon-btn ${showText ? 'active' : ''}`}
            onClick={() => setShowText(v => !v)}
            title={showText ? 'Hide keyboard' : 'Type instead'}
          >
            <Keyboard size={16} />
          </button>
        )}

        {/* Text input (secondary) */}
        {showText && sessionStarted && (
          <div className="text-input-overlay">
            <TextInput onSend={sendText} disabled={!connected} />
          </div>
        )}
      </div>
    </div>
  )
}
