import TaskItem from './TaskItem.jsx'
import { Clock } from 'lucide-react'

export default function DeadlinesSection({ items, windowDays }) {
  const cutoff = new Date()
  cutoff.setDate(cutoff.getDate() + windowDays)

  const visible = items.filter(t => !t.due_date || new Date(t.due_date) <= cutoff)
  const overdue = visible.filter(t => t.due_date && new Date(t.due_date) < new Date())
  const upcoming = visible.filter(t => !t.due_date || new Date(t.due_date) >= new Date())

  return (
    <section className="dashboard-section">
      <div className="section-header">
        <Clock size={16} />
        <h3>Hard Deadlines</h3>
        {visible.length > 0 && <span className="badge">{visible.length}</span>}
      </div>
      {visible.length === 0 ? (
        <p className="empty-state">No upcoming deadlines</p>
      ) : (
        <ul className="task-list">
          {overdue.map(task => <TaskItem key={task.id} task={task} overdue />)}
          {upcoming.map(task => <TaskItem key={task.id} task={task} />)}
        </ul>
      )}
    </section>
  )
}
