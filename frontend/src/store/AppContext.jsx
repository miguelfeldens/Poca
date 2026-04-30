import { createContext, useContext, useState, useCallback } from 'react'

const AppContext = createContext(null)

export function AppProvider({ children }) {
  const [tasks, setTasks] = useState([])
  const [calendarEvents, setCalendarEvents] = useState([])
  const [sessionId, setSessionId] = useState(null)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [pendingCalendarEvent, setPendingCalendarEvent] = useState(null)
  const [pendingSearch, setPendingSearch] = useState(null)
  const [aiPriorities, setAiPriorities] = useState([])

  const addTask = useCallback((task) => {
    setTasks(prev => {
      const exists = prev.some(t => t.id === task.id)
      return exists ? prev : [task, ...prev]
    })
  }, [])

  const removeTask = useCallback((taskId) => {
    setTasks(prev => prev.filter(t => t.id !== taskId))
  }, [])

  const markTaskComplete = useCallback((taskId) => {
    setTasks(prev => prev.map(t => t.id === taskId ? { ...t, is_completed: true } : t))
  }, [])

  const updateTasks = useCallback((newTasks) => {
    setTasks(prev => {
      const map = new Map(prev.map(t => [t.id, t]))
      newTasks.forEach(t => map.set(t.id, t))
      return Array.from(map.values())
    })
  }, [])

  return (
    <AppContext.Provider value={{
      tasks, setTasks, addTask, removeTask, markTaskComplete, updateTasks,
      calendarEvents, setCalendarEvents,
      sessionId, setSessionId,
      settingsOpen, setSettingsOpen,
      pendingCalendarEvent, setPendingCalendarEvent,
      pendingSearch, setPendingSearch,
      aiPriorities, setAiPriorities,
    }}>
      {children}
    </AppContext.Provider>
  )
}

export function useApp() {
  return useContext(AppContext)
}
