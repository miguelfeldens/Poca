import TaskItem from './TaskItem.jsx'
import { ListTodo } from 'lucide-react'

export default function ActionItemsSection({ items }) {
  return (
    <section className="dashboard-section">
      <div className="section-header">
        <ListTodo size={16} />
        <h3>Open Action Items</h3>
        {items.length > 0 && <span className="badge">{items.length}</span>}
      </div>
      {items.length === 0 ? (
        <p className="empty-state">No open action items</p>
      ) : (
        <ul className="task-list">
          {items.map(task => <TaskItem key={task.id} task={task} />)}
        </ul>
      )}
    </section>
  )
}
