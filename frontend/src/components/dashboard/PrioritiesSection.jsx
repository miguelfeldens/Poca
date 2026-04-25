import TaskItem from './TaskItem.jsx'
import { Target } from 'lucide-react'

export default function PrioritiesSection({ items }) {
  return (
    <section className="dashboard-section">
      <div className="section-header">
        <Target size={16} />
        <h3>Top Priorities</h3>
        {items.length > 0 && <span className="badge">{items.length}</span>}
      </div>
      {items.length === 0 ? (
        <p className="empty-state">No active priorities</p>
      ) : (
        <ul className="task-list">
          {items.map(task => <TaskItem key={task.id} task={task} />)}
        </ul>
      )}
    </section>
  )
}
