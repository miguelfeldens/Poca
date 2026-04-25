import { Calendar } from 'lucide-react'
import { formatEventTime } from '../../utils/formatters.js'

export default function CalendarSection({ events }) {
  return (
    <section className="dashboard-section">
      <div className="section-header">
        <Calendar size={16} />
        <h3>Calendar</h3>
        {events.length > 0 && <span className="badge">{events.length}</span>}
      </div>
      {events.length === 0 ? (
        <p className="empty-state">No upcoming events</p>
      ) : (
        <ul className="event-list">
          {events.map(event => (
            <li key={event.id} className="event-item">
              <div className="event-time">{formatEventTime(event.start)}</div>
              <div className="event-title">{event.title}</div>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
