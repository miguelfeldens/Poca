import { useState } from 'react'
import { useAuth } from '../../store/AuthContext.jsx'
import api from '../../services/api.js'

const VOICES = ['Aoede', 'Charon', 'Fenrir', 'Kore', 'Puck']

export default function PreferencesForm() {
  const { user, loadUser } = useAuth()
  const [form, setForm] = useState({
    voice_preference: user?.voice_preference || 'Aoede',
    dashboard_window_days: user?.dashboard_window_days || 3,
    voice_output_enabled: user?.voice_output_enabled ?? true,
    celebration_sounds: user?.celebration_sounds ?? true,
  })
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  const handleSave = async () => {
    setSaving(true)
    try {
      await api.patch('/users/me/settings', form)
      await loadUser()
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch {
      // Non-fatal
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="settings-section">
      <div className="form-group">
        <label>Voice</label>
        <select
          value={form.voice_preference}
          onChange={e => setForm(f => ({ ...f, voice_preference: e.target.value }))}
        >
          {VOICES.map(v => <option key={v} value={v}>{v}</option>)}
        </select>
      </div>

      <div className="form-group">
        <label>Dashboard window</label>
        <select
          value={form.dashboard_window_days}
          onChange={e => setForm(f => ({ ...f, dashboard_window_days: Number(e.target.value) }))}
        >
          <option value={3}>3 days (today + 2)</option>
          <option value={7}>7 days</option>
          <option value={14}>14 days</option>
          <option value={30}>30 days</option>
        </select>
      </div>

      <div className="form-group toggle-group">
        <label>Voice output</label>
        <button
          className={`toggle ${form.voice_output_enabled ? 'on' : 'off'}`}
          onClick={() => setForm(f => ({ ...f, voice_output_enabled: !f.voice_output_enabled }))}
          role="switch"
          aria-checked={form.voice_output_enabled}
        >
          <span />
        </button>
      </div>

      <div className="form-group toggle-group">
        <label>Celebration sounds</label>
        <button
          className={`toggle ${form.celebration_sounds ? 'on' : 'off'}`}
          onClick={() => setForm(f => ({ ...f, celebration_sounds: !f.celebration_sounds }))}
          role="switch"
          aria-checked={form.celebration_sounds}
        >
          <span />
        </button>
      </div>

      <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
        {saved ? 'Saved!' : saving ? 'Saving…' : 'Save preferences'}
      </button>
    </div>
  )
}
