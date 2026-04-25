import { format } from 'date-fns'

export default function MessageBubble({ message }) {
  const { role, content, timestamp } = message
  const isUser = role === 'user'
  const isSystem = role === 'system'

  if (isSystem) {
    return <div className="system-message">{content}</div>
  }

  return (
    <div className={`message ${isUser ? 'user' : 'assistant'}`}>
      {!isUser && <div className="poca-avatar-sm">P</div>}
      <div className="bubble">
        <p>{content}</p>
        <span className="msg-time">{format(new Date(timestamp), 'h:mm a')}</span>
      </div>
    </div>
  )
}
