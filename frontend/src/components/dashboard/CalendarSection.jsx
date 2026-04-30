import { Calendar, ExternalLink } from 'lucide-react'
import { format, isToday, isTomorrow } from 'date-fns'

function formatTime(dateStr) {
  if (!dateStr) return ''
  return format(new Date(dateStr), 'h:mm a')
}

function dateLabel(dateStr) {
  const d = new Date(dateStr)
  if (isToday(d)) return 'Today'
  if (isTomorrow(d)) return 'Tomorrow'
  return format(d, 'EEE, MMM d')
}

function groupByDate(events) {
  const groups = []
  let currentLabel = null
  for (const event of events) {
    const label = dateLabel(event.start)
    if (label !== currentLabel) {
      groups.push({ label, events: [] })
      currentLabel = label
    }
    groups[groups.length - 1].events.push(event)
  }
  return groups
}

export default function CalendarSection({ events }) {
  const groups = groupByDate(events)

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
        <div className="event-list">
          {groups.map((group, i) => (
            <div key={group.label} className="event-date-group">
              {i > 0 && <hr className="date-divider" />}
              <div className="date-label">{group.label}</div>
              <ul className="date-events">
                {group.events.map(event => (
                  <li key={event.id} className="event-item">
                    {event.html_link ? (
                      <a href={event.html_link} target="_blank" rel="noopener noreferrer" className="event-link">
                        <span className="event-time">{formatTime(event.start)}</span>
                        <span className="event-title">{event.title}<ExternalLink size={11} className="link-icon" /></span>
                      </a>
                    ) : (
                      <>
                        <span className="event-time">{formatTime(event.start)}</span>
                        <span className="event-title">{event.title}</span>
                      </>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
