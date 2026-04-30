import TaskItem from './TaskItem.jsx'
import { Clock } from 'lucide-react'
import { isToday } from 'date-fns'

function urgency(task) {
  if (!task.due_date) return 'future'
  const due = new Date(task.due_date)
  const now = new Date()
  if (due < now) return 'overdue'
  if (isToday(due)) return 'today'
  return 'future'
}

export default function DeadlinesSection({ items }) {
  // Sort: overdue first, then today, then future (by due date ascending)
  const sorted = [...items].sort((a, b) => {
    const order = { overdue: 0, today: 1, future: 2 }
    const ua = order[urgency(a)], ub = order[urgency(b)]
    if (ua !== ub) return ua - ub
    return new Date(a.due_date || '9999') - new Date(b.due_date || '9999')
  })

  return (
    <section className="dashboard-section">
      <div className="section-header">
        <Clock size={16} />
        <h3>Hard Deadlines</h3>
        {items.length > 0 && <span className="badge">{items.length}</span>}
      </div>
      {items.length === 0 ? (
        <p className="empty-state">No deadlines</p>
      ) : (
        <ul className="task-list">
          {sorted.map(task => (
            <TaskItem key={task.id} task={task} urgency={urgency(task)} />
          ))}
        </ul>
      )}
    </section>
  )
}
