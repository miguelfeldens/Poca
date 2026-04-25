import { useState } from 'react'
import { useApp } from '../../store/AppContext.jsx'
import api from '../../services/api.js'

export default function SearchConfirmModal() {
  const { pendingSearch, setPendingSearch } = useApp()
  const [loading, setLoading] = useState(false)

  if (!pendingSearch) return null

  const handleConfirm = async () => {
    setLoading(true)
    try {
      await api.post('/search/web', { query: pendingSearch, save_to_context: true })
    } catch {
      // Non-fatal
    } finally {
      setLoading(false)
      setPendingSearch(null)
    }
  }

  return (
    <div className="modal-overlay">
      <div className="modal-card">
        <h3>Search the web?</h3>
        <p className="search-query">"{pendingSearch}"</p>
        <p className="search-note">Results will be saved to your context (expires in 7 days).</p>
        <div className="modal-actions">
          <button className="btn btn-secondary" onClick={() => setPendingSearch(null)}>Cancel</button>
          <button className="btn btn-primary" onClick={handleConfirm} disabled={loading}>
            {loading ? 'Searching…' : 'Search'}
          </button>
        </div>
      </div>
    </div>
  )
}
