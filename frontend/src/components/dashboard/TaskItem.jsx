import { useState } from 'react'
import { Trash2, Check } from 'lucide-react'
import { useApp } from '../../store/AppContext.jsx'
import { useAuth } from '../../store/AuthContext.jsx'
import { formatDueDate, isOverdue } from '../../utils/formatters.js'
import { playCelebration } from '../../utils/sounds.js'
import api from '../../services/api.js'

export default function TaskItem({ task, overdue, urgency }) {
  const { removeTask, markTaskComplete } = useApp()
  const { user } = useAuth()
  const [confirming, setConfirming] = useState(false)

  const handleComplete = async () => {
    try {
      await api.patch(`/tasks/${task.id}`, { is_completed: true })
      markTaskComplete(task.id)
      if (user?.celebration_sounds !== false) {
        playCelebration()
      }
    } catch {
      // Non-fatal
    }
  }

  const handleDelete = async () => {
    if (!confirming) {
      setConfirming(true)
      setTimeout(() => setConfirming(false), 3000)
      return
    }
    try {
      await api.delete(`/tasks/${task.id}`)
      removeTask(task.id)
    } catch {
      // Non-fatal
    }
  }

  const dueLabel = formatDueDate(task.due_date)
  const overdueFlag = overdue || (task.due_date && isOverdue(task.due_date))

  return (
    <li className={`task-item ${overdueFlag ? 'overdue' : ''}`}>
      {urgency && <span className={`urgency-dot urgency-${urgency}`} />}
      <button className="task-complete-btn" onClick={handleComplete} aria-label="Mark complete">
        <Check size={14} />
      </button>
      <div className="task-content">
        <span className="task-title">{task.title}</span>
        {dueLabel && (
          <span className={`task-due ${overdueFlag ? 'overdue-label' : ''}`}>{dueLabel}</span>
        )}
      </div>
      <button
        className={`task-delete-btn ${confirming ? 'confirming' : ''}`}
        onClick={handleDelete}
        aria-label={confirming ? 'Click again to confirm delete' : 'Delete task'}
        title={confirming ? 'Click again to confirm' : 'Delete'}
      >
        <Trash2 size={14} />
      </button>
    </li>
  )
}
