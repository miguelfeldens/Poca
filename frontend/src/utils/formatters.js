import { format, isToday, isTomorrow, isPast, formatDistanceToNow } from 'date-fns'

export function formatDueDate(dateStr) {
  if (!dateStr) return null
  const date = new Date(dateStr)
  if (isToday(date)) return `Today ${format(date, 'h:mm a')}`
  if (isTomorrow(date)) return `Tomorrow ${format(date, 'h:mm a')}`
  if (isPast(date)) return `Overdue — ${format(date, 'MMM d')}`
  return format(date, 'MMM d, h:mm a')
}

export function formatEventTime(dateStr) {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  if (isToday(date)) return `Today ${format(date, 'h:mm a')}`
  return format(date, 'EEE MMM d, h:mm a')
}

export function isOverdue(dateStr) {
  if (!dateStr) return false
  return isPast(new Date(dateStr))
}

export function isDueToday(dateStr) {
  if (!dateStr) return false
  return isToday(new Date(dateStr))
}
