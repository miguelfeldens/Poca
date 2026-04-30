import { Target } from 'lucide-react'

export default function PrioritiesSection({ items }) {
  return (
    <section className="dashboard-section">
      <div className="section-header">
        <Target size={16} />
        <h3>AI Priorities</h3>
      </div>
      {items.length === 0 ? (
        <p className="empty-state">Priorities appear when you start a session</p>
      ) : (
        <ol className="priorities-list">
          {items.map((text, i) => (
            <li key={i} className="priority-item">{text}</li>
          ))}
        </ol>
      )}
    </section>
  )
}
