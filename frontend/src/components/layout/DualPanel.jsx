import { useState } from 'react'
import ConversationPanel from './ConversationPanel.jsx'
import DashboardPanel from './DashboardPanel.jsx'
import { useApp } from '../../store/AppContext.jsx'
import { Settings } from 'lucide-react'

export default function DualPanel() {
  const { setSettingsOpen } = useApp()
  const [mobileView, setMobileView] = useState('chat') // 'chat' | 'dashboard'

  return (
    <div className="dual-panel">
      {/* Header */}
      <header className="app-header">
        <div className="header-left">
          <span className="brand">POCA</span>
        </div>
        {/* Mobile tab toggle */}
        <div className="mobile-tabs">
          <button
            className={`tab-btn ${mobileView === 'chat' ? 'active' : ''}`}
            onClick={() => setMobileView('chat')}
          >
            Chat
          </button>
          <button
            className={`tab-btn ${mobileView === 'dashboard' ? 'active' : ''}`}
            onClick={() => setMobileView('dashboard')}
          >
            Dashboard
          </button>
        </div>
        <button
          className="icon-btn settings-btn"
          onClick={() => setSettingsOpen(true)}
          aria-label="Settings"
        >
          <Settings size={20} />
        </button>
      </header>

      {/* Panels */}
      <div className="panels-container">
        <div className={`panel panel-left ${mobileView === 'chat' ? 'mobile-visible' : 'mobile-hidden'}`}>
          <ConversationPanel />
        </div>
        <div className={`panel panel-right ${mobileView === 'dashboard' ? 'mobile-visible' : 'mobile-hidden'}`}>
          <DashboardPanel />
        </div>
      </div>
    </div>
  )
}
