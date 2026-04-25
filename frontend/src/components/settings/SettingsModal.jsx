import { useState } from 'react'
import { X } from 'lucide-react'
import { useApp } from '../../store/AppContext.jsx'
import PreferencesForm from './PreferencesForm.jsx'
import ContextEditor from './ContextEditor.jsx'

const TABS = ['Preferences', 'Context', 'Calendar']

export default function SettingsModal() {
  const { setSettingsOpen } = useApp()
  const [activeTab, setActiveTab] = useState('Preferences')

  return (
    <div className="modal-overlay" onClick={(e) => e.target === e.currentTarget && setSettingsOpen(false)}>
      <div className="modal-card settings-modal">
        <div className="modal-header">
          <h2>Settings</h2>
          <button className="icon-btn" onClick={() => setSettingsOpen(false)} aria-label="Close">
            <X size={20} />
          </button>
        </div>

        <div className="settings-tabs">
          {TABS.map(tab => (
            <button
              key={tab}
              className={`tab-btn ${activeTab === tab ? 'active' : ''}`}
              onClick={() => setActiveTab(tab)}
            >
              {tab}
            </button>
          ))}
        </div>

        <div className="settings-content">
          {activeTab === 'Preferences' && <PreferencesForm />}
          {activeTab === 'Context' && <ContextEditor />}
          {activeTab === 'Calendar' && <CalendarSettings />}
        </div>
      </div>
    </div>
  )
}

function CalendarSettings() {
  return (
    <div className="settings-section">
      <h3>Google Calendar</h3>
      <p>Your Google Calendar is connected via OAuth. POCA can read events and add new ones with your confirmation.</p>
      <p className="settings-note">To disconnect, revoke access at <a href="https://myaccount.google.com/permissions" target="_blank" rel="noopener noreferrer">Google Account Permissions</a>.</p>
    </div>
  )
}
