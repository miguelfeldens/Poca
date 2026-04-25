import { useEffect } from 'react'
import { useAuth } from '../store/AuthContext.jsx'
import { useApp } from '../store/AppContext.jsx'
import DualPanel from '../components/layout/DualPanel.jsx'
import SettingsModal from '../components/settings/SettingsModal.jsx'
import CalendarConfirmModal from '../components/conversation/CalendarConfirmModal.jsx'
import SearchConfirmModal from '../components/conversation/SearchConfirmModal.jsx'
import api from '../services/api.js'

export default function Main() {
  const { user } = useAuth()
  const { setTasks, setCalendarEvents, settingsOpen, pendingCalendarEvent, pendingSearch } = useApp()

  // Load initial data
  useEffect(() => {
    const loadData = async () => {
      try {
        const [tasksRes, calendarRes] = await Promise.allSettled([
          api.get('/tasks/'),
          api.get('/calendar/events?days_ahead=30'),
        ])
        if (tasksRes.status === 'fulfilled') setTasks(tasksRes.value.data)
        if (calendarRes.status === 'fulfilled') setCalendarEvents(calendarRes.value.data)
      } catch {
        // Non-fatal
      }
    }
    loadData()
  }, [setTasks, setCalendarEvents])

  return (
    <div className="app-container">
      <DualPanel />
      {settingsOpen && <SettingsModal />}
      {pendingCalendarEvent && <CalendarConfirmModal />}
      {pendingSearch && <SearchConfirmModal />}
    </div>
  )
}
