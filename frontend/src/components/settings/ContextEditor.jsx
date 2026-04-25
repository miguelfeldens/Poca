import { useState, useEffect } from 'react'
import { Trash2, Plus, RefreshCw, Upload, Link } from 'lucide-react'
import api from '../../services/api.js'

export default function ContextEditor() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [addMode, setAddMode] = useState(null) // null | 'url' | 'upload'
  const [newUrl, setNewUrl] = useState('')
  const [newTitle, setNewTitle] = useState('')
  const [newType, setNewType] = useState('url')
  const [uploading, setUploading] = useState(false)

  useEffect(() => {
    loadItems()
  }, [])

  const loadItems = async () => {
    setLoading(true)
    try {
      const res = await api.get('/context/')
      setItems(res.data)
    } catch {
      // Non-fatal
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (id) => {
    try {
      await api.delete(`/context/${id}`)
      setItems(prev => prev.filter(i => i.id !== id))
    } catch {
      // Non-fatal
    }
  }

  const handleResync = async (id) => {
    try {
      const res = await api.post(`/context/${id}/resync`)
      setItems(prev => prev.map(i => i.id === id ? res.data : i))
    } catch {
      // Non-fatal
    }
  }

  const handleAddUrl = async () => {
    if (!newUrl.trim() || !newTitle.trim()) return
    try {
      const res = await api.post('/context/link', {
        item_type: newType,
        title: newTitle.trim(),
        source_url: newUrl.trim(),
      })
      setItems(prev => [res.data, ...prev])
      setNewUrl('')
      setNewTitle('')
      setAddMode(null)
    } catch {
      // Non-fatal
    }
  }

  const handleUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('title', file.name.replace('.pdf', ''))
      const res = await api.post('/context/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setItems(prev => [res.data, ...prev])
      setAddMode(null)
    } catch {
      // Non-fatal
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="context-editor">
      <div className="context-editor-header">
        <h3>Loaded Context</h3>
        <div className="context-add-btns">
          <button className="btn btn-sm" onClick={() => setAddMode('url')}>
            <Link size={14} /> Add URL / Doc
          </button>
          <button className="btn btn-sm" onClick={() => setAddMode('upload')}>
            <Upload size={14} /> Upload PDF
          </button>
        </div>
      </div>

      {addMode === 'url' && (
        <div className="add-form">
          <input
            type="text"
            placeholder="Title"
            value={newTitle}
            onChange={e => setNewTitle(e.target.value)}
          />
          <input
            type="url"
            placeholder="URL (Google Doc, Sheet, or any URL)"
            value={newUrl}
            onChange={e => setNewUrl(e.target.value)}
          />
          <select value={newType} onChange={e => setNewType(e.target.value)}>
            <option value="url">Web URL</option>
            <option value="google_doc">Google Doc</option>
            <option value="google_sheet">Google Sheet</option>
          </select>
          <div className="add-form-actions">
            <button className="btn btn-sm btn-secondary" onClick={() => setAddMode(null)}>Cancel</button>
            <button className="btn btn-sm btn-primary" onClick={handleAddUrl}>Add</button>
          </div>
        </div>
      )}

      {addMode === 'upload' && (
        <div className="add-form">
          <label className="file-upload-label">
            <Upload size={16} />
            {uploading ? 'Uploading…' : 'Choose PDF file'}
            <input type="file" accept=".pdf" onChange={handleUpload} hidden />
          </label>
          <button className="btn btn-sm btn-secondary" onClick={() => setAddMode(null)}>Cancel</button>
        </div>
      )}

      {loading ? (
        <p className="loading-text">Loading context…</p>
      ) : items.length === 0 ? (
        <p className="empty-state">No context loaded yet. Add documents, links, or PDFs to give POCA more context about your world.</p>
      ) : (
        <ul className="context-list">
          {items.map(item => (
            <li key={item.id} className="context-item">
              <div className="context-item-info">
                <span className="context-type-badge">{item.item_type}</span>
                <span className="context-title">{item.title}</span>
                {item.auto_expires_at && (
                  <span className="expires-badge">expires in 7d</span>
                )}
              </div>
              <div className="context-item-actions">
                {item.source_url && (
                  <button className="icon-btn" onClick={() => handleResync(item.id)} title="Re-sync">
                    <RefreshCw size={14} />
                  </button>
                )}
                <button className="icon-btn danger" onClick={() => handleDelete(item.id)} title="Remove">
                  <Trash2 size={14} />
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
