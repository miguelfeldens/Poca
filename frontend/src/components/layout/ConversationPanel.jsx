import { useEffect, useRef } from 'react'
import { useGeminiLive } from '../../hooks/useGeminiLive.js'
import MessageList from '../conversation/MessageList.jsx'
import TextInput from '../conversation/TextInput.jsx'
import VoiceButton from '../conversation/VoiceButton.jsx'
import { useAuth } from '../../store/AuthContext.jsx'
import { Power } from 'lucide-react'

export default function ConversationPanel() {
  const { user } = useAuth()
  const { messages, connected, pocaTyping, connect, disconnect, sendText, sendAudio } = useGeminiLive()
  const hasConnected = useRef(false)

  // Auto-connect on mount
  useEffect(() => {
    if (!hasConnected.current) {
      hasConnected.current = true
      connect()
    }
    return () => { disconnect() }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="conversation-panel">
      {/* Status bar */}
      <div className="conversation-header">
        <div className="user-info">
          {user?.avatar_url && (
            <img src={user.avatar_url} alt={user.name} className="avatar" />
          )}
          <span className="user-name">Hi, {user?.name?.split(' ')[0]}!</span>
        </div>
        <div className="connection-status">
          <span className={`status-dot ${connected ? 'online' : 'offline'}`} />
          <span>{connected ? 'Connected' : 'Disconnected'}</span>
          {!connected && (
            <button className="reconnect-btn icon-btn" onClick={connect} title="Reconnect">
              <Power size={14} />
            </button>
          )}
        </div>
      </div>

      {/* Messages */}
      <MessageList messages={messages} typing={pocaTyping} />

      {/* Input area */}
      <div className="input-area">
        <VoiceButton onTranscript={sendText} onAudioChunk={sendAudio} />
        <TextInput onSend={sendText} disabled={!connected} />
      </div>
    </div>
  )
}
