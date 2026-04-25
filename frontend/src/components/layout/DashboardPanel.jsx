import { useApp } from '../../store/AppContext.jsx'
import { useAuth } from '../../store/AuthContext.jsx'
import PrioritiesSection from '../dashboard/PrioritiesSection.jsx'
import DeadlinesSection from '../dashboard/DeadlinesSection.jsx'
import ActionItemsSection from '../dashboard/ActionItemsSection.jsx'
import CalendarSection from '../dashboard/CalendarSection.jsx'

export default function DashboardPanel() {
  const { user } = useAuth()
  const { tasks, calendarEvents } = useApp()
  const windowDays = user?.dashboard_window_days || 3

  const priorities = tasks.filter(t => t.task_type === 'priority' && !t.is_completed)
  const deadlines = tasks.filter(t => t.task_type === 'deadline' && !t.is_completed)
  const actionItems = tasks.filter(t => t.task_type === 'action_item' && !t.is_completed)

  // Filter calendar events to display window
  const cutoff = new Date()
  cutoff.setDate(cutoff.getDate() + windowDays)
  const upcomingEvents = calendarEvents.filter(e => new Date(e.start) <= cutoff)

  return (
    <div className="dashboard-panel">
      <div className="dashboard-header">
        <h2>Dashboard</h2>
        <span className="window-label">Next {windowDays} days</span>
      </div>

      <div className="dashboard-sections">
        <PrioritiesSection items={priorities} />
        <DeadlinesSection items={deadlines} windowDays={windowDays} />
        <ActionItemsSection items={actionItems} />
        <CalendarSection events={upcomingEvents} />
      </div>
    </div>
  )
}
