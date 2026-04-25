import { useState } from 'react'

const API_BASE = import.meta.env.VITE_API_URL || '/api'

export default function Login() {
  const [passphrase, setPassphrase] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleGoogleLogin = async (e) => {
    e.preventDefault()
    if (!passphrase.trim()) {
      setError('Please enter your invite passphrase.')
      return
    }
    setLoading(true)
    setError('')
    // Redirect to backend Google OAuth with passphrase
    window.location.href = `${API_BASE}/auth/google?passphrase=${encodeURIComponent(passphrase)}`
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-logo">
          <span className="logo-text">POCA</span>
          <span className="logo-tagline">Personal Organization and Cheeky Aid</span>
        </div>

        <form onSubmit={handleGoogleLogin} className="auth-form">
          <div className="form-group">
            <label htmlFor="passphrase">Invite Passphrase</label>
            <input
              id="passphrase"
              type="password"
              value={passphrase}
              onChange={(e) => setPassphrase(e.target.value)}
              placeholder="Enter your invite passphrase"
              autoComplete="off"
              required
            />
          </div>

          {error && <div className="error-message">{error}</div>}

          <button
            type="submit"
            className="btn btn-google"
            disabled={loading}
          >
            <GoogleIcon />
            {loading ? 'Redirecting…' : 'Continue with Google'}
          </button>
        </form>

        <p className="auth-note">
          POCA is invite-only. You need a passphrase to sign in.<br />
          Your Google account is required for Calendar integration.
        </p>
      </div>
    </div>
  )
}

function GoogleIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
      <path d="M17.64 9.2a10.3 10.3 0 00-.16-1.84H9v3.48h4.84a4.14 4.14 0 01-1.8 2.72v2.26h2.92c1.7-1.57 2.68-3.88 2.68-6.62z" fill="#4285F4"/>
      <path d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.92-2.26c-.8.54-1.83.86-3.04.86-2.34 0-4.32-1.58-5.03-3.7H.96v2.34A8.997 8.997 0 009 18z" fill="#34A853"/>
      <path d="M3.97 10.72A5.41 5.41 0 013.69 9c0-.6.1-1.18.28-1.72V4.94H.96A8.997 8.997 0 000 9c0 1.45.35 2.82.96 4.06l3.01-2.34z" fill="#FBBC05"/>
      <path d="M9 3.58c1.32 0 2.5.45 3.44 1.34l2.58-2.58C13.46.89 11.43 0 9 0A8.997 8.997 0 00.96 4.94l3.01 2.34C4.68 5.16 6.66 3.58 9 3.58z" fill="#EA4335"/>
    </svg>
  )
}
