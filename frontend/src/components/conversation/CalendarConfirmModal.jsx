import { useApp } from '../../store/AppContext.jsx'
import { format } from 'date-fns'
import api from '../../services/api.js'

export default function CalendarConfirmModal() {
  const { pendingCalendarEvent, setPendingCalendarEvent, setCalendarEvents } = useApp()

  if (!pendingCalendarEvent) return null

  const handleConfirm = async () => {
    try {
      const res = await api.post('/calendar/events', {
        title: pendingCalendarEvent.title,
        start: pendingCalendarEvent.start,
        end: pendingCalendarEvent.end,
        description: pendingCalendarEvent.description,
      })
      setCalendarEvents(prev => [...prev, res.data])
    } catch {
      // Non-fatal
    }
    setPendingCalendarEvent(null)
  }

  const start = pendingCalendarEvent.start ? new Date(pendingCalendarEvent.start) : null

  return (
    <div className="modal-overlay">
      <div className="modal-card">
        <h3>Add to Google Calendar?</h3>
        <div className="event-preview">
          <strong>{pendingCalendarEvent.title}</strong>
          {start && <p>{format(start, 'EEEE, MMMM d • h:mm a')}</p>}
          {pendingCalendarEvent.description && <p>{pendingCalendarEvent.description}</p>}
        </div>
        <div className="modal-actions">
          <button className="btn btn-secondary" onClick={() => setPendingCalendarEvent(null)}>Cancel</button>
          <button className="btn btn-primary" onClick={handleConfirm}>Add to Calendar</button>
        </div>
      </div>
    </div>
  )
}
