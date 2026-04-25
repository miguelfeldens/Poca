import { useEffect, useRef } from 'react'
import MessageBubble from './MessageBubble.jsx'

export default function MessageList({ messages, typing }) {
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, typing])

  return (
    <div className="message-list">
      {messages.length === 0 && (
        <div className="welcome-placeholder">
          <div className="poca-avatar">P</div>
          <p>Connecting to POCA…</p>
        </div>
      )}
      {messages.map(msg => (
        <MessageBubble key={msg.id} message={msg} />
      ))}
      {typing && (
        <div className="message assistant typing-indicator">
          <div className="bubble">
            <span /><span /><span />
          </div>
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  )
}
